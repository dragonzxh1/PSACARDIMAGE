"""
卡牌图像处理工具
用于去除背景、矫正卡牌方向并裁剪出卡牌部分
使用传统图像处理方法（OTSU阈值、轮廓检测、透视变换）
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import argparse


class CardImageProcessor:
    """卡牌图像处理器"""
    
    def __init__(self, edge_threshold1: int = 50, edge_threshold2: int = 150):
        """
        初始化处理器
        
        Args:
            edge_threshold1: Canny边缘检测低阈值
            edge_threshold2: Canny边缘检测高阈值
        """
        self.edge_threshold1 = edge_threshold1
        self.edge_threshold2 = edge_threshold2
    
    def detect_card_contour(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        检测卡牌轮廓（针对透明塑料评级壳优化）
        核心思路：识别最外层的塑料壳轮廓，而不是卡片内部图案
        
        Args:
            image: 输入图像（BGR格式）
            
        Returns:
            卡牌轮廓（4个顶点的四边形），如果找到，否则返回None
        """
        h, w = image.shape[:2]
        
        # 第一步：图像预处理
        # 灰度化
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 高斯模糊：减少背景纹理干扰，保留卡壳边缘反光
        # 使用较大的核来抹平桌垫纹理
        blurred = cv2.GaussianBlur(gray, (9, 9), 0)
        
        # 第二步：二值化（优先于Canny，因为背景是深黑，卡壳是浅色/反光）
        # 方案A：OTSU自动阈值（推荐）
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 方案B：如果OTSU效果不好，尝试固定阈值
        # 因为背景是深黑，卡壳是浅色，可以尝试较低的阈值
        # _, binary = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY)
        
        # 形态学操作：填充内部空洞，连接断开的边缘
        kernel = np.ones((5, 5), np.uint8)
        # 闭运算：先膨胀后腐蚀，填充卡壳内部的小空洞
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)
        # 膨胀：连接可能断开的边缘
        dilated = cv2.dilate(closed, kernel, iterations=2)
        
        # 第三步：查找轮廓
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            # 如果没找到轮廓，尝试使用Canny作为备用
            edges = cv2.Canny(blurred, 50, 150)
            dilated_edges = cv2.dilate(edges, kernel, iterations=3)
            contours, _ = cv2.findContours(dilated_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # 筛选轮廓：找到最大的轮廓（应该是塑料壳）
        # 面积阈值：至少占图像的10%
        min_area = h * w * 0.10
        max_area = h * w * 0.95
        
        valid_contours = [c for c in contours if min_area < cv2.contourArea(c) < max_area]
        
        if not valid_contours:
            # 如果没找到，降低阈值
            min_area = h * w * 0.05
            valid_contours = [c for c in contours if min_area < cv2.contourArea(c) < max_area]
        
        if not valid_contours:
            return None
        
        # 选择最大的轮廓（塑料壳应该是最外层的最大轮廓）
        largest_contour = max(valid_contours, key=cv2.contourArea)
        
        # 第四步：多边形拟合 - 将轮廓拟合为四边形
        # 逐步调整epsilon，直到得到4个顶点
        epsilon_start = 0.01
        epsilon_end = 0.1
        epsilon_step = 0.01
        
        best_approx = None
        best_epsilon = epsilon_start
        
        for epsilon in np.arange(epsilon_start, epsilon_end, epsilon_step):
            epsilon_val = epsilon * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon_val, True)
            
            if len(approx) == 4:
                best_approx = approx
                best_epsilon = epsilon
                break
            elif len(approx) > 4 and best_approx is None:
                # 如果顶点数大于4，记录最接近4的情况
                best_approx = approx
                best_epsilon = epsilon
        
        # 如果找到了4个顶点，返回
        if best_approx is not None and len(best_approx) == 4:
            return best_approx
        
        # 如果拟合后不是4个顶点，使用最小外接矩形
        rect = cv2.minAreaRect(largest_contour)
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        
        # 转换为4个点的格式
        return box.reshape(-1, 1, 2)
    
    def _detect_with_hough_lines(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        使用霍夫线变换作为备用方法检测矩形
        
        Args:
            image: 输入图像
            
        Returns:
            检测到的矩形轮廓，如果失败返回None
        """
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Canny边缘检测
        edges = cv2.Canny(blurred, 50, 150)
        
        # 霍夫线变换检测直线
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, 
                                minLineLength=min(h, w)//4, maxLineGap=20)
        
        if lines is None or len(lines) < 4:
            # 如果霍夫线变换也失败，使用图像中心区域作为卡牌区域
            # 假设卡牌占据图像中心80%的区域
            margin_x = int(w * 0.1)
            margin_y = int(h * 0.1)
            corners = np.array([
                [margin_x, margin_y],  # 左上
                [w - margin_x, margin_y],  # 右上
                [w - margin_x, h - margin_y],  # 右下
                [margin_x, h - margin_y]  # 左下
            ], dtype=np.float32)
            return corners.reshape(-1, 1, 2)
        
        # 将直线分组为水平和垂直方向
        horizontal_lines = []
        vertical_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            
            if angle < 30 or angle > 150:  # 水平线
                horizontal_lines.append((x1, y1, x2, y2))
            elif 60 < angle < 120:  # 垂直线
                vertical_lines.append((x1, y1, x2, y2))
        
        if len(horizontal_lines) < 2 or len(vertical_lines) < 2:
            # 如果线不够，使用中心区域
            margin_x = int(w * 0.1)
            margin_y = int(h * 0.1)
            corners = np.array([
                [margin_x, margin_y],
                [w - margin_x, margin_y],
                [w - margin_x, h - margin_y],
                [margin_x, h - margin_y]
            ], dtype=np.float32)
            return corners.reshape(-1, 1, 2)
        
        # 找到最上和最下的水平线，最左和最右的垂直线
        top_line = min(horizontal_lines, key=lambda l: min(l[1], l[3]))
        bottom_line = max(horizontal_lines, key=lambda l: max(l[1], l[3]))
        left_line = min(vertical_lines, key=lambda l: min(l[0], l[2]))
        right_line = max(vertical_lines, key=lambda l: max(l[0], l[2]))
        
        # 计算四个交点
        def line_intersection(line1, line2):
            """计算两条线的交点"""
            x1, y1, x2, y2 = line1
            x3, y3, x4, y4 = line2
            
            denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(denom) < 1e-10:
                return None
            
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            return (int(x), int(y))
        
        # 计算四个角点
        corners = []
        for h_line in [top_line, bottom_line]:
            for v_line in [left_line, right_line]:
                point = line_intersection(h_line, v_line)
                if point:
                    corners.append(point)
        
        if len(corners) == 4:
            corners = np.array(corners, dtype=np.float32)
            return corners.reshape(-1, 1, 2)
        
        # 如果交点计算失败，使用中心区域
        margin_x = int(w * 0.1)
        margin_y = int(h * 0.1)
        corners = np.array([
            [margin_x, margin_y],
            [w - margin_x, margin_y],
            [w - margin_x, h - margin_y],
            [margin_x, h - margin_y]
        ], dtype=np.float32)
        return corners.reshape(-1, 1, 2)
    
    def get_card_corners(self, contour: np.ndarray) -> np.ndarray:
        """
        从轮廓中提取卡牌的四个角点
        
        Args:
            contour: 卡牌轮廓
            
        Returns:
            四个角点的坐标数组（float32格式，用于透视变换）
        """
        # 如果轮廓已经有4个点，直接使用
        if len(contour) == 4:
            corners = contour.reshape(4, 2).astype(np.float32)
        else:
            # 否则，找到最小外接矩形
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            corners = box.astype(np.float32)
        
        # 对点进行排序：左上、右上、右下、左下
        return self._order_points(corners)
    
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        对四个点进行排序：左上、右上、右下、左下
        
        Args:
            pts: 四个点的坐标（float32格式）
            
        Returns:
            排序后的点（float32格式）
        """
        # 确保输入是float32格式
        pts = pts.astype(np.float32)
        
        # 初始化结果数组
        rect = np.zeros((4, 2), dtype=np.float32)
        
        # 左上角点：x+y最小
        # 右下角点：x+y最大
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # 左上
        rect[2] = pts[np.argmax(s)]  # 右下
        
        # 右上角点：x-y最小（或x最大且y较小）
        # 左下角点：x-y最大（或x最小且y较大）
        diff = np.diff(pts, axis=1).flatten()
        rect[1] = pts[np.argmin(diff)]  # 右上
        rect[3] = pts[np.argmax(diff)]  # 左下
        
        # 验证排序：确保左上和右下不是同一个点
        if np.array_equal(rect[0], rect[2]):
            # 如果相同，使用x坐标重新排序
            sorted_pts = pts[np.argsort(pts[:, 0])]
            rect[0] = sorted_pts[0]  # 最左
            rect[2] = sorted_pts[-1]  # 最右
            sorted_pts_y = pts[np.argsort(pts[:, 1])]
            rect[1] = sorted_pts_y[0]  # 最上
            rect[3] = sorted_pts_y[-1]  # 最下
        
        return rect
    
    def calculate_card_dimensions(self, corners: np.ndarray) -> Tuple[int, int]:
        """
        计算卡牌的目标尺寸
        
        Args:
            corners: 四个角点
            
        Returns:
            (宽度, 高度)
        """
        # 计算宽度（取上下两边的平均值）
        width_a = np.sqrt(((corners[1][0] - corners[0][0]) ** 2) + 
                          ((corners[1][1] - corners[0][1]) ** 2))
        width_b = np.sqrt(((corners[2][0] - corners[3][0]) ** 2) + 
                          ((corners[2][1] - corners[3][1]) ** 2))
        width = max(int(width_a), int(width_b))
        
        # 计算高度（取左右两边的平均值）
        height_a = np.sqrt(((corners[3][0] - corners[0][0]) ** 2) + 
                           ((corners[3][1] - corners[0][1]) ** 2))
        height_b = np.sqrt(((corners[2][0] - corners[1][0]) ** 2) + 
                           ((corners[2][1] - corners[1][1]) ** 2))
        height = max(int(height_a), int(height_b))
        
        return width, height
    
    def perspective_transform(self, image: np.ndarray, corners: np.ndarray, 
                             add_rounded_corners: bool = False, 
                             corner_radius: int = 20) -> np.ndarray:
        """
        对图像进行透视变换，矫正卡牌方向
        
        Args:
            image: 输入图像（可以是 BGR 或 BGRA 格式）
            corners: 四个角点（已排序：左上、右上、右下、左下）
            add_rounded_corners: 是否添加圆角透明背景
            corner_radius: 圆角半径（像素）
            
        Returns:
            矫正后的图像（如果add_rounded_corners=True或输入有Alpha通道，返回带Alpha通道的图像）
        """
        # 计算目标尺寸
        width, height = self.calculate_card_dimensions(corners)
        
        # 确保尺寸合理
        if width <= 0 or height <= 0:
            print(f"  警告：计算出的尺寸无效 ({width}x{height})，使用原始图像")
            return image
        
        # 定义目标点（输出图像的四个角）
        dst = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]
        ], dtype=np.float32)
        
        # 计算透视变换矩阵
        M = cv2.getPerspectiveTransform(corners, dst)
        
        # 应用透视变换
        # 如果图像有 Alpha 通道，需要指定 flags 参数
        flags = cv2.INTER_LINEAR
        if len(image.shape) == 3 and image.shape[2] == 4:
            # 有 Alpha 通道，使用 INTER_LINEAR 并保持 Alpha
            warped = cv2.warpPerspective(image, M, (width, height), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        else:
            warped = cv2.warpPerspective(image, M, (width, height), flags=flags)
        
        # 如果需要添加圆角透明背景
        if add_rounded_corners:
            # 创建Alpha通道掩膜
            mask = np.zeros((height, width), dtype=np.uint8)
            
            # 绘制圆角矩形（白色区域表示保留的部分）
            # 方法：先绘制完整的矩形，然后在四个角绘制圆形来形成圆角
            # 绘制中心矩形（去除四个角）
            cv2.rectangle(mask, (corner_radius, 0), 
                         (width - corner_radius, height), 255, -1)
            cv2.rectangle(mask, (0, corner_radius), 
                         (width, height - corner_radius), 255, -1)
            
            # 绘制四个圆角
            cv2.circle(mask, (corner_radius, corner_radius), corner_radius, 255, -1)
            cv2.circle(mask, (width - corner_radius, corner_radius), corner_radius, 255, -1)
            cv2.circle(mask, (width - corner_radius, height - corner_radius), corner_radius, 255, -1)
            cv2.circle(mask, (corner_radius, height - corner_radius), corner_radius, 255, -1)
            
            # 将BGR图像转换为BGRA（添加Alpha通道）
            if len(warped.shape) == 3 and warped.shape[2] == 3:
                bgra = cv2.cvtColor(warped, cv2.COLOR_BGR2BGRA)
            elif len(warped.shape) == 3 and warped.shape[2] == 4:
                bgra = warped.copy()
            else:
                bgra = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGRA)
            
            # 应用掩膜到Alpha通道
            bgra[:, :, 3] = mask
            
            return bgra
        
        return warped
    
    def process_image(self, image_path: Path, output_path: Optional[Path] = None, 
                     save_debug: bool = False, add_rounded_corners: bool = False,
                     corner_radius: int = 20) -> Optional[Path]:
        """
        处理单张图像
        
        Args:
            image_path: 输入图像路径
            output_path: 输出图像路径（如果为None，则在原路径添加_processed后缀）
            save_debug: 是否保存调试图像（显示检测到的轮廓）
            add_rounded_corners: 是否添加圆角透明背景（保存为PNG格式）
            corner_radius: 圆角半径（像素）
            
        Returns:
            输出图像路径（如果成功），否则返回None
        """
        # 读取图像
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"错误：无法读取图像 {image_path}")
            return None
        
        print(f"正在处理: {image_path.name}")
        print(f"  原始尺寸: {image.shape[1]}x{image.shape[0]}")
        
        # 检测卡牌轮廓
        contour = self.detect_card_contour(image)
        
        # 使用原始图像进行透视变换
        source_image = image
        
        if contour is None:
            print(f"  警告：未检测到卡牌轮廓，使用图像中心区域作为卡牌")
            # 如果检测失败，使用图像中心80%区域作为卡牌
            h, w = source_image.shape[:2]
            margin_x = int(w * 0.1)
            margin_y = int(h * 0.1)
            corners = np.array([
                [margin_x, margin_y],  # 左上
                [w - margin_x, margin_y],  # 右上
                [w - margin_x, h - margin_y],  # 右下
                [margin_x, h - margin_y]  # 左下
            ], dtype=np.float32)
            processed = self.perspective_transform(source_image, corners,
                                                  add_rounded_corners=add_rounded_corners,
                                                  corner_radius=corner_radius)
            print(f"  处理后尺寸: {processed.shape[1]}x{processed.shape[0]}")
        else:
            # 提取角点
            corners = self.get_card_corners(contour)
            
            # 确保角点坐标在图像范围内
            h, w = source_image.shape[:2]
            corners[:, 0] = np.clip(corners[:, 0], 0, w - 1)
            corners[:, 1] = np.clip(corners[:, 1], 0, h - 1)
            
            print(f"  检测到轮廓，角点坐标:")
            for i, corner in enumerate(corners):
                print(f"    角点 {i}: ({corner[0]:.1f}, {corner[1]:.1f})")
            
            # 透视变换
            processed = self.perspective_transform(source_image, corners,
                                                  add_rounded_corners=add_rounded_corners,
                                                  corner_radius=corner_radius)
            print(f"  处理后尺寸: {processed.shape[1]}x{processed.shape[0]}")
            
            # 保存调试图像（使用原始图像显示轮廓，便于查看）
            if save_debug:
                debug_image = image.copy()
                cv2.drawContours(debug_image, [contour], -1, (0, 255, 0), 3)
                for i, corner in enumerate(corners):
                    corner_int = tuple(corner.astype(int))
                    cv2.circle(debug_image, corner_int, 10, (0, 0, 255), -1)
                    cv2.putText(debug_image, str(i), corner_int, 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                
                debug_path = image_path.parent / f"{image_path.stem}_debug{image_path.suffix}"
                cv2.imwrite(str(debug_path), debug_image)
                print(f"  调试图像已保存: {debug_path.name}")
        
        # 确定输出路径
        if output_path is None:
            # 如果添加了圆角（有Alpha通道），保存为PNG格式以支持透明背景
            if add_rounded_corners or (len(processed.shape) == 3 and processed.shape[2] == 4):
                output_path = image_path.parent / f"{image_path.stem}_processed.png"
            else:
                output_path = image_path.parent / f"{image_path.stem}_processed{image_path.suffix}"
        
        # 保存处理后的图像
        # 如果图像有Alpha通道，使用PNG格式
        if len(processed.shape) == 4 or (len(processed.shape) == 3 and processed.shape[2] == 4):
            success = cv2.imwrite(str(output_path), processed)
        else:
            success = cv2.imwrite(str(output_path), processed)
        if success:
            print(f"  ✓ 处理完成: {output_path.name}")
            return output_path
        else:
            print(f"  ✗ 保存失败: {output_path}")
            return None
    
    def process_directory(self, directory: Path, output_dir: Optional[Path] = None,
                         pattern: str = "*.jpg", save_debug: bool = False,
                         add_rounded_corners: bool = False, corner_radius: int = 20) -> int:
        """
        批量处理目录中的图像
        
        Args:
            directory: 输入目录
            output_dir: 输出目录（如果为None，则在原目录创建processed子目录）
            pattern: 文件匹配模式
            save_debug: 是否保存调试图像
            
        Returns:
            成功处理的图像数量
        """
        # 查找所有图像文件
        image_files = list(directory.glob(pattern))
        image_files.extend(list(directory.glob("*.jpeg")))
        image_files.extend(list(directory.glob("*.png")))
        
        # 过滤掉已处理的文件
        image_files = [f for f in image_files if "_processed" not in f.name and "_debug" not in f.name]
        
        if not image_files:
            print(f"在 {directory} 中未找到图像文件")
            return 0
        
        print(f"\n找到 {len(image_files)} 张图像")
        
        # 确定输出目录
        if output_dir is None:
            output_dir = directory / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 处理每张图像
        success_count = 0
        for image_file in image_files:
            if add_rounded_corners:
                output_path = output_dir / f"{image_file.stem}_processed.png"
            else:
                output_path = output_dir / f"{image_file.stem}_processed{image_file.suffix}"
            result = self.process_image(image_file, output_path, save_debug,
                                       add_rounded_corners=add_rounded_corners,
                                       corner_radius=corner_radius)
            if result:
                success_count += 1
            print()
        
        print(f"\n处理完成: {success_count}/{len(image_files)} 张图像成功处理")
        return success_count


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="卡牌图像处理工具 - 去除背景并矫正方向")
    parser.add_argument("input", type=str, help="输入图像文件或目录路径")
    parser.add_argument("-o", "--output", type=str, default=None, 
                       help="输出路径（文件或目录，默认为输入路径添加_processed后缀）")
    parser.add_argument("-d", "--debug", action="store_true", 
                       help="保存调试图像（显示检测到的轮廓）")
    parser.add_argument("--threshold1", type=int, default=50,
                       help="Canny边缘检测低阈值（默认：50）")
    parser.add_argument("--threshold2", type=int, default=150,
                       help="Canny边缘检测高阈值（默认：150）")
    parser.add_argument("--rounded-corners", action="store_true",
                       help="添加圆角透明背景（保存为PNG格式）")
    parser.add_argument("--corner-radius", type=int, default=20,
                       help="圆角半径（像素，默认：20）")
    
    args = parser.parse_args()
    
    # 创建处理器
    processor = CardImageProcessor(
        edge_threshold1=args.threshold1,
        edge_threshold2=args.threshold2
    )
    
    # 处理输入
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：路径不存在: {input_path}")
        return
    
    if input_path.is_file():
        # 处理单张图像
        output_path = Path(args.output) if args.output else None
        processor.process_image(input_path, output_path, args.debug,
                               add_rounded_corners=args.rounded_corners,
                               corner_radius=args.corner_radius)
    elif input_path.is_dir():
        # 批量处理
        output_dir = Path(args.output) if args.output else None
        processor.process_directory(input_path, output_dir, save_debug=args.debug,
                                   add_rounded_corners=args.rounded_corners,
                                   corner_radius=args.corner_radius)
    else:
        print(f"错误：无效的路径: {input_path}")


if __name__ == "__main__":
    main()

