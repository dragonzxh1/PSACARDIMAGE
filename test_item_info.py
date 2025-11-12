"""
PSA Item Information 提取测试工具
用于测试和调试 Item Information 的抓取功能
"""

import sys
from pathlib import Path
from psa_item_info_extractor import PSAItemInfoExtractor
from psa_card_downloader import PSACardImageDownloader


def test_single_certificate(cert_number: str, save_html: bool = False):
    """
    测试单个证书的 Item Information 提取
    
    Args:
        cert_number: 证书编号
        save_html: 是否保存HTML文件用于调试
    """
    print("=" * 80)
    print(f"测试证书编号: {cert_number}")
    print("=" * 80)
    
    # 初始化下载器和提取器
    downloader = PSACardImageDownloader()
    extractor = PSAItemInfoExtractor()
    
    try:
        # 提取证书编号
        extracted_num = downloader._extract_cert_number(cert_number)
        print(f"提取的证书编号: {extracted_num}")
        print()
        
        # 获取页面HTML
        print("正在获取页面HTML...")
        html = downloader._get_page_html(extracted_num)
        print(f"HTML长度: {len(html)} 字符")
        
        # 保存HTML文件（用于调试）
        if save_html:
            html_file = Path(f"test_html_{extracted_num}.html")
            html_file.write_text(html, encoding='utf-8')
            print(f"HTML已保存到: {html_file}")
        
        print()
        print("-" * 80)
        print("开始提取 Item Information...")
        print("-" * 80)
        
        # 提取 Item Information
        item_info = extractor.extract_item_info(html)
        
        # 显示提取结果
        print()
        print("提取结果:")
        print("=" * 80)
        if item_info:
            print(f"找到 {len(item_info)} 个字段:")
            print()
            for key, value in item_info.items():
                print(f"  {key}: {value}")
        else:
            print("未找到任何 Item Information 字段")
        
        print()
        print("=" * 80)
        
        # 提取 Brand/Title
        brand_title = extractor.get_brand_title(item_info)
        print()
        print("Brand/Title 提取结果:")
        print("-" * 80)
        if brand_title:
            print(f"  Brand/Title: {brand_title}")
        else:
            print("  未找到 Brand/Title")
        
        print()
        print("=" * 80)
        
        # 保存测试结果
        test_dir = Path("test_results")
        test_dir.mkdir(exist_ok=True)
        
        # 保存文本格式
        text_file = extractor.save_item_info_text(item_info, test_dir, extracted_num)
        print(f"测试结果已保存到: {text_file}")
        
        # 保存JSON格式
        json_file = extractor.save_item_info(item_info, test_dir, extracted_num)
        print(f"JSON结果已保存到: {json_file}")
        
        return item_info, brand_title
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None


def test_multiple_certificates(cert_numbers: list, save_html: bool = False):
    """
    测试多个证书的 Item Information 提取
    
    Args:
        cert_numbers: 证书编号列表
        save_html: 是否保存HTML文件用于调试
    """
    print("=" * 80)
    print(f"批量测试 {len(cert_numbers)} 个证书")
    print("=" * 80)
    print()
    
    results = []
    
    for i, cert_num in enumerate(cert_numbers, 1):
        print(f"\n[{i}/{len(cert_numbers)}] 测试证书: {cert_num}")
        print("-" * 80)
        
        item_info, brand_title = test_single_certificate(cert_num, save_html)
        
        results.append({
            'cert_number': cert_num,
            'item_info': item_info,
            'brand_title': brand_title,
            'found': item_info is not None and len(item_info) > 0
        })
        
        print()
        print("=" * 80)
        print()
    
    # 显示汇总结果
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    print()
    
    found_count = sum(1 for r in results if r['found'])
    print(f"成功提取: {found_count}/{len(results)}")
    print(f"失败: {len(results) - found_count}/{len(results)}")
    print()
    
    print("详细结果:")
    print("-" * 80)
    for result in results:
        status = "✓" if result['found'] else "✗"
        brand_title_str = result['brand_title'] if result['brand_title'] else "未找到"
        fields_count = len(result['item_info']) if result['item_info'] else 0
        print(f"{status} {result['cert_number']}: {fields_count} 个字段, Brand/Title: {brand_title_str}")
    
    return results


def main():
    """主函数"""
    print("PSA Item Information 提取测试工具")
    print("=" * 80)
    print()
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python test_item_info.py <证书编号1> [证书编号2] [证书编号3] ...")
        print()
        print("示例:")
        print("  python test_item_info.py 96098359")
        print("  python test_item_info.py 96098359 78928691 12345678")
        print()
        print("选项:")
        print("  --save-html    保存HTML文件用于调试")
        print()
        
        # 如果没有参数，使用默认测试证书
        print("使用默认测试证书: 96098359")
        print()
        test_single_certificate("96098359", save_html='--save-html' in sys.argv)
    else:
        # 解析参数
        cert_numbers = []
        save_html = False
        
        for arg in sys.argv[1:]:
            if arg == '--save-html':
                save_html = True
            else:
                cert_numbers.append(arg)
        
        if not cert_numbers:
            print("错误: 请提供至少一个证书编号")
            return
        
        if len(cert_numbers) == 1:
            test_single_certificate(cert_numbers[0], save_html)
        else:
            test_multiple_certificates(cert_numbers, save_html)


if __name__ == "__main__":
    main()

