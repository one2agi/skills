#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
证据册智能排版与生成器（呈堂级高保真极简素雅公文版 · 一页式多证明目的精准映射）
严格遵循 .agents/skills/evidence-booklet/SKILL.md 规范：
1. 1-to-1 编号审计与主动阻断
2. 卷首一页式《原告提交的〈证据目录〉》，多证明目的与页码一一对应细分（rowspan=7）
3. 纯粹正文四要素铁律：证明目的、证据*:标题、证明内容、证据图片
4. 彻底剔除色块填充、冗余聊天记录转写、多余图片图注
5. 精确默认工程参数（上34pt/下30pt/左30pt/右24pt，栏宽260.9pt，间距19.5pt，字号12.5pt/11.5pt/10.0pt）
6. 顺序顺延合并证据二（民事裁定书）与证据三（信用卡流水凭证）
7. 全局统一矢量居中连贯页码（第 X 页 / 共 54 页）及全套 PDF 目录书签
"""

import os
import sys
import re
import subprocess
import html
from PIL import Image
import fitz

WORKSPACE_DIR = '/mnt/d/Users/morav/Desktop/证据证明'
MD_PATH = os.path.join(WORKSPACE_DIR, '开庭文件/MD文件/证据册.md')
IMG_DIR = os.path.join(WORKSPACE_DIR, '案件整理/2-证据体系/证据图片/证明图片')
COURT_RULING_PDF = os.path.join(WORKSPACE_DIR, '开庭文件/民事裁定书.pdf')
V5_PDF = os.path.join(WORKSPACE_DIR, '开庭文件/证据册_合并版_v5.pdf')
OUT_PDF_PATH = os.path.join(WORKSPACE_DIR, '开庭文件/证据册.pdf')

TMP_HTML_PATH = '/home/morav/evidence_booklet_tmp.html'
TMP_PDF_BODY = '/home/morav/evidence_booklet_body_raw.pdf'

def clean_obsidian_tags(text):
    """彻底清除 Obsidian 块引用 ID 与多余尾部标记"""
    if not text:
        return ""
    text = re.sub(r'\^[a-zA-Z0-9_\-]+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def strip_markdown(text):
    """去除 Markdown 符号，用于纯文本输出"""
    if not text:
        return ""
    text = clean_obsidian_tags(text)
    text = text.replace('**', '').replace('__', '')
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()

def stage_1_audit(md_path, img_dir):
    """
    第一阶段：前置 1-to-1 编号审计与主动阻断协议（硬性防御）
    """
    print("=" * 60)
    print("【第一阶段】执行前置 1-to-1 编号审计...")
    
    if not os.path.exists(md_path):
        print(f"❌ 阻断：未找到证据册 Markdown 文件: {md_path}")
        sys.exit(1)
    if not os.path.exists(img_dir):
        print(f"❌ 阻断：未找到证据图片目录: {img_dir}")
        sys.exit(1)
        
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
        
    ev_matches = list(re.finditer(r'###\s+证据(\d+)[：:]([^\n]+)', md_text))
    md_ev_map = {}
    for m in ev_matches:
        num = int(m.group(1))
        title = m.group(2).strip()
        md_ev_map[num] = title
        
    img_files = [f for f in os.listdir(img_dir) if not f.startswith('.')]
    img_map = {}
    invalid_format_files = []
    
    for f in img_files:
        m = re.match(r'^(\d+)(?:-(\d+))?\.(jpg|jpeg|png)$', f, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            sub = int(m.group(2)) if m.group(2) else 0
            img_map.setdefault(num, []).append((sub, f))
        else:
            invalid_format_files.append(f)
            
    missing_imgs = [num for num in md_ev_map if num not in img_map]
    orphan_imgs = [num for num in img_map if num not in md_ev_map]
    
    md_nums = sorted(list(md_ev_map.keys()))
    sequence_breaks = [i for i in range(1, max(md_nums) + 1) if i not in md_ev_map]
    
    audit_passed = True
    audit_errors = []
    
    if missing_imgs:
        audit_passed = False
        for m in missing_imgs:
            audit_errors.append((f"证据 {m}", "证据图片缺失", f"Markdown 中有条目，但图片目录缺少对应图片", f"请添加截图并命名为 {m}.*"))
    if orphan_imgs:
        audit_passed = False
        for o in orphan_imgs:
            audit_errors.append((f"图片编号 {o}", "孤儿未登记图片", f"图片目录下存在文件，但在 Markdown 中未登记", f"请核实是否遗漏或删除废弃文件"))
    if invalid_format_files:
        audit_passed = False
        for inv in invalid_format_files:
            audit_errors.append((inv, "命名符号异常", f"文件名不符合规范（应为 N.* 或 N-sub.*）", f"请重命名"))
    if sequence_breaks:
        audit_passed = False
        audit_errors.append((f"跳号 {sequence_breaks}", "编号跳号或断裂", f"证据编号存在逻辑断层", f"请核对证据编号连续性"))
        
    if not audit_passed:
        print("\n⚠️ 【证据册前置审计未通过：发现编号不匹配，排版已暂停】\n")
        print("| 序号 | 证据编号 / 文件名 | 异常类型 | 详细说明 | 建议处理动作 |")
        print("|:---|:---|:---|:---|:---|")
        for idx, err in enumerate(audit_errors, 1):
            print(f"| {idx} | {err[0]} | **{err[1]}** | {err[2]} | {err[3]} |")
        print("\n请手动核对并修正文件编号，确认 1-to-1 对应无误后重新指示排版。")
        sys.exit(1)
        
    print(f"✅ 前置 1-to-1 编号审计 100% 通过！")
    print(f"   * 登记证据总数: {len(md_ev_map)} 项 (证据1 ~ 证据{max(md_nums)})")
    print(f"   * 图片总数: {len(img_files)} 张，完全匹配无任何孤儿或缺失")
    print("=" * 60)
    return md_text, img_map

def parse_markdown_and_images(md_text, img_map, img_dir):
    """
    第二阶段：结构化解析证明目的与证据项（纯粹四要素）
    """
    p_matches = list(re.finditer(r'##\s+证明目的([一二三四五六七八九十\d]+)[：:]([^\n]+)', md_text))
    sections = []
    
    for i, match in enumerate(p_matches):
        p_num_str = match.group(1).strip()
        p_title = match.group(2).strip()
        start_pos = match.end()
        end_pos = p_matches[i+1].start() if i+1 < len(p_matches) else len(md_text)
        p_content = md_text[start_pos:end_pos]
        
        ev_matches = list(re.finditer(r'###\s+证据(\d+)[：:]([^\n]+)', p_content))
        ev_list = []
        for j, em in enumerate(ev_matches):
            e_num = int(em.group(1))
            e_title = em.group(2).strip()
            e_start = em.end()
            e_end = ev_matches[j+1].start() if j+1 < len(ev_matches) else len(p_content)
            e_block = p_content[e_start:e_end].strip()
            
            next_p = re.search(r'\n##\s+证明目的', e_block)
            if next_p:
                e_block = e_block[:next_p.start()]
                
            proof_match = re.search(r'\*\*【证明内容】\*\*\s*([^\n]+(?:\n(?!\*\*上下文|\`\`\`)[^\n]+)*)', e_block)
            raw_proof = proof_match.group(1).strip() if proof_match else ''
            proof_text = clean_obsidian_tags(raw_proof)
            
            if '被告自述' in e_title:
                source = '被告提交自述书证'
            elif '证人和生' in e_title or '和生' in e_title:
                source = '证人和生微信记录'
            elif '证人阿狼' in e_title or '阿狼' in e_title:
                source = '证人阿狼微信记录'
            elif '被告小号' in e_title:
                source = '微信记录(被告小号)'
            elif '银行' in e_title:
                source = '银行电子回单'
            elif '支付宝' in e_title:
                source = '支付宝官方账单'
            else:
                source = '原被告微信聊天记录'
                
            raw_imgs = sorted(img_map.get(e_num, []), key=lambda x: x[0])
            imgs_data = []
            for sub, fname in raw_imgs:
                fpath = os.path.join(img_dir, fname)
                with Image.open(fpath) as im:
                    w, h = im.size
                    ratio = w / h
                imgs_data.append({
                    'sub': sub,
                    'filename': fname,
                    'path': fpath,
                    'width': w,
                    'height': h,
                    'ratio': ratio,
                    'is_wide': (ratio >= 1.05)
                })
                
            ev_list.append({
                'num': e_num,
                'title': e_title,
                'source': source,
                'proof': proof_text,
                'images': imgs_data,
                'purpose_num': p_num_str,
                'purpose_title': p_title
            })
            
        sections.append({
            'p_num_str': p_num_str,
            'p_title': p_title,
            'evidences': ev_list
        })
        
    return sections

def plan_pages(sections):
    """
    第三阶段：弹性自适应页面规划算法
    严格执行：
    1. 目录占第 1 页，正文从第 2 页起始
    2. 容量底线：每页最多 2 张图片
    3. 证明目的绝不跨目混排，保持顺序递增
    4. 动态计算每个证明目的在正文中的起止页码 (start_p, end_p)
    """
    pages = []
    evidence_page_map = {}
    purpose_page_ranges = {}
    
    current_global_page = 2 # 目录占第 1 页，正文从第 2 页开始
    
    for s in sections:
        p_num_str = s['p_num_str']
        p_title = s['p_title']
        ev_list = s['evidences']
        
        p_start_page = current_global_page
        
        idx = 0
        while idx < len(ev_list):
            ev = ev_list[idx]
            imgs = ev['images']
            
            if len(imgs) == 2:
                # 场景 2：单证据双竖图
                page_data = {
                    'purpose_num': p_num_str,
                    'purpose_title': p_title,
                    'type': 'single_dual_tall',
                    'evidences': [ev]
                }
                pages.append(page_data)
                evidence_page_map[ev['num']] = current_global_page
                current_global_page += 1
                idx += 1
            elif len(imgs) == 1 and imgs[0]['is_wide']:
                # 场景 3：横版宽图/大凭据通栏独占
                page_data = {
                    'purpose_num': p_num_str,
                    'purpose_title': p_title,
                    'type': 'single_wide',
                    'evidences': [ev]
                }
                pages.append(page_data)
                evidence_page_map[ev['num']] = current_global_page
                current_global_page += 1
                idx += 1
            elif len(imgs) == 1 and not imgs[0]['is_wide']:
                # 尝试与下一个单竖图配对
                if idx + 1 < len(ev_list):
                    next_ev = ev_list[idx + 1]
                    next_imgs = next_ev['images']
                    if len(next_imgs) == 1 and not next_imgs[0]['is_wide']:
                        # 场景 1：双证据双栏对仗
                        page_data = {
                            'purpose_num': p_num_str,
                            'purpose_title': p_title,
                            'type': 'dual_column',
                            'evidences': [ev, next_ev]
                        }
                        pages.append(page_data)
                        evidence_page_map[ev['num']] = current_global_page
                        evidence_page_map[next_ev['num']] = current_global_page
                        current_global_page += 1
                        idx += 2
                        continue
                # 场景 4：单证据单竖图居左留白
                page_data = {
                    'purpose_num': p_num_str,
                    'purpose_title': p_title,
                    'type': 'single_tall_left',
                    'evidences': [ev]
                }
                pages.append(page_data)
                evidence_page_map[ev['num']] = current_global_page
                current_global_page += 1
                idx += 1
            else:
                page_data = {
                    'purpose_num': p_num_str,
                    'purpose_title': p_title,
                    'type': 'single_tall_left',
                    'evidences': [ev]
                }
                pages.append(page_data)
                evidence_page_map[ev['num']] = current_global_page
                current_global_page += 1
                idx += 1
                
        p_end_page = current_global_page - 1
        purpose_page_ranges[p_num_str] = (p_start_page, p_end_page)
        
    return pages, evidence_page_map, purpose_page_ranges

def format_proof_html(text):
    if not text:
        return ""
    text = clean_obsidian_tags(text)
    text = html.escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    return text

def generate_html(sections, pages, evidence_page_map, purpose_page_ranges, appendix_ranges):
    """
    第四阶段与第五阶段：按截图排版结构生成一页式《证据目录》与素雅正文 HTML
    """
    css_content = """
    @page {
        size: 595.28pt 841.89pt;
        margin: 0;
    }
    *, *::before, *::after {
        box-sizing: border-box;
    }
    body {
        margin: 0;
        padding: 0;
        background: #f1f5f9;
        font-family: "Noto Sans CJK SC", "Noto Serif CJK SC", "PingFang SC", "SimSun", sans-serif;
        color: #000000;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    .page {
        width: 595.28pt;
        height: 841.89pt;
        max-height: 841.89pt;
        min-height: 841.89pt;
        page-break-after: always;
        break-after: page;
        padding: 34pt 24pt 30pt 30pt;
        background: #ffffff;
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        margin: 0 auto;
    }
    @media screen {
        .page {
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }
    }
    
    /* 目录页样式（精确复刻截图结构） */
    .catalog-title-screenshot {
        font-size: 22pt;
        font-weight: 700;
        text-align: center;
        margin-top: 20pt;
        margin-bottom: 25pt;
        letter-spacing: 2px;
        color: #000000;
        font-family: "Noto Sans CJK SC", "SimHei", sans-serif;
    }
    .catalog-table-screenshot {
        width: 100%;
        border-collapse: collapse;
        border: 1pt solid #cbd5e1;
        font-size: 10pt;
    }
    .catalog-table-screenshot th {
        background-color: #f1f5f9;
        color: #000000;
        font-weight: 700;
        padding: 9pt 8pt;
        border: 1pt solid #cbd5e1;
        text-align: center;
        font-size: 10.5pt;
    }
    .catalog-table-screenshot td {
        padding: 6.5pt 8pt;
        border: 1pt solid #cbd5e1;
        vertical-align: middle;
        color: #1e293b;
        line-height: 1.4;
    }
    .cell-center {
        text-align: center;
        font-weight: 500;
    }
    .cell-bold {
        font-weight: 600;
        color: #000000;
    }
    .cell-purpose {
        text-align: left;
        font-size: 9.5pt;
    }
    
    /* 正文页样式 (完全对齐 v5 第二页素雅标准) */
    .purpose-header-v5 {
        font-size: 12.5pt;
        font-weight: bold;
        color: #000000;
        font-family: "Noto Sans CJK SC", "SimHei", sans-serif;
        line-height: 1.3;
        margin-bottom: 6pt;
        border-bottom: 0.5pt solid #d1d5db;
        padding-bottom: 5pt;
        letter-spacing: 0.2pt;
    }
    .body-content-v5 {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    
    /* 双栏对仗 (栏宽 260.9pt, 间隙 19.5pt) */
    .dual-grid-v5 {
        display: grid;
        grid-template-columns: 260.9pt 260.9pt;
        gap: 19.5pt;
        height: 100%;
        min-height: 0;
    }
    .col-v5 {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        overflow: hidden;
    }
    .ev-title-v5 {
        font-size: 11.5pt;
        font-weight: bold;
        color: #000000;
        font-family: "Noto Sans CJK SC", "SimHei", sans-serif;
        line-height: 1.3;
        margin-bottom: 6pt;
        word-break: break-word;
    }
    .ev-proof-v5 {
        font-size: 10.0pt;
        font-weight: normal;
        color: #000000;
        font-family: "Noto Sans CJK SC", "Noto Serif CJK SC", sans-serif;
        line-height: 1.4;
        text-align: justify;
        margin-bottom: 8pt;
        word-break: break-word;
    }
    .ev-img-box-v5 {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        overflow: hidden;
    }
    .ev-img-v5 {
        width: 100%;
        max-width: 260.9pt;
        max-height: 100%;
        object-fit: contain;
        border: 0.5pt solid #e2e8f0;
    }
    
    /* 场景 2：单证据双竖图横向并排 */
    .dual-img-container-v5 {
        flex: 1;
        min-height: 0;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        gap: 19.5pt;
        overflow: hidden;
        margin-top: 4pt;
    }
    .dual-img-col-v5 {
        width: 260.9pt;
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        overflow: hidden;
    }
    
    /* 场景 3：横版宽图通栏独占 */
    .wide-img-container-v5 {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        margin-top: 6pt;
    }
    .wide-img-v5 {
        max-width: 540pt;
        max-height: 100%;
        object-fit: contain;
        border: 0.5pt solid #e2e8f0;
    }
    
    /* 场景 4：单竖图居左留白 */
    .single-left-container-v5 {
        display: grid;
        grid-template-columns: 260.9pt 260.9pt;
        gap: 19.5pt;
        height: 100%;
        min-height: 0;
    }
    """
    
    html_pages = []
    
    # ---------------- 渲染第 1 页《原告提交的〈证据目录〉》（截图精准对齐） ----------------
    cat_page = """
    <div class="page">
        <div class="catalog-title-screenshot">原告提交的《证据目录》</div>
        <table class="catalog-table-screenshot">
            <thead>
                <tr>
                    <th style="width: 10%;">序号</th>
                    <th style="width: 22%;">证据名称</th>
                    <th style="width: 48%;">证明目的</th>
                    <th style="width: 10%;">页码</th>
                    <th style="width: 10%;">来源</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # 证据一：跨 7 行合并，证明目的与页码划分为 7 个子格一一对应
    for idx, s in enumerate(sections):
        p_num = s['p_num_str']
        p_title = s['p_title']
        prange = purpose_page_ranges.get(p_num, (2, 42))
        prange_str = f"P{prange[0]}-P{prange[1]}" if prange[0] != prange[1] else f"P{prange[0]}"
        
        full_purpose_text = f"证明目的{p_num}：{p_title}；" if idx < len(sections) - 1 else f"证明目的{p_num}：{p_title}。"
        
        if idx == 0:
            cat_page += f"""
                <tr>
                    <td rowspan="7" class="cell-center">证据一</td>
                    <td rowspan="7" class="cell-center cell-bold">微信聊天记录及被告自述材料汇总</td>
                    <td class="cell-purpose">{html.escape(full_purpose_text)}</td>
                    <td class="cell-center">{prange_str}</td>
                    <td rowspan="7" class="cell-center">原告</td>
                </tr>
            """
        else:
            cat_page += f"""
                <tr>
                    <td class="cell-purpose">{html.escape(full_purpose_text)}</td>
                    <td class="cell-center">{prange_str}</td>
                </tr>
            """
            
    # 证据二：民事裁定书
    ev2_range_str = f"P{appendix_ranges['ev2'][0]}-P{appendix_ranges['ev2'][1]}"
    cat_page += f"""
                <tr>
                    <td class="cell-center">证据二</td>
                    <td class="cell-center cell-bold">《民事裁定书》（撤诉）</td>
                    <td class="cell-purpose">证明原告曾向法院提起诉讼并申请撤诉，本案诉讼时效依法中断，未超过法定诉讼时效。</td>
                    <td class="cell-center">{ev2_range_str}</td>
                    <td class="cell-center">原告</td>
                </tr>
    """
    
    # 证据三：信用卡流水凭单
    ev3_range_str = f"P{appendix_ranges['ev3'][0]}-P{appendix_ranges['ev3'][1]}"
    cat_page += f"""
                <tr>
                    <td class="cell-center">证据三</td>
                    <td class="cell-center cell-bold">信用卡账单及扣款流水凭证</td>
                    <td class="cell-purpose">1. 证明被告使用原告信用卡发生的本金 24,370 元及固定利息 2,737.05 元的具体金额；</td>
                    <td class="cell-center">{ev3_range_str}</td>
                    <td class="cell-center">原告</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    html_pages.append(cat_page)
    
    # ---------------- 渲染正文 41 页 (纯粹四要素) ----------------
    for p_idx, page in enumerate(pages, 1):
        p_type = page['type']
        p_num_str = page['purpose_num']
        p_title = page['purpose_title']
        evs = page['evidences']
        
        page_html = f"""
        <div class="page">
            <div class="purpose-header-v5">证明目的{p_num_str}：{html.escape(p_title)}</div>
            <div class="body-content-v5">
        """
        
        if p_type == 'dual_column':
            ev1, ev2 = evs[0], evs[1]
            page_html += """<div class="dual-grid-v5">"""
            for ev in [ev1, ev2]:
                img_data = ev['images'][0]
                page_html += f"""
                    <div class="col-v5">
                        <div class="ev-title-v5">证据{ev['num']}：{html.escape(ev['title'])}</div>
                        <div class="ev-proof-v5">证明内容：{format_proof_html(ev['proof'])}</div>
                        <div class="ev-img-box-v5">
                            <img class="ev-img-v5" src="{img_data['path']}">
                        </div>
                    </div>
                """
            page_html += """</div>"""
            
        elif p_type == 'single_dual_tall':
            ev = evs[0]
            img1, img2 = ev['images'][0], ev['images'][1]
            page_html += f"""
                <div class="col-v5">
                    <div class="ev-title-v5">证据{ev['num']}：{html.escape(ev['title'])}</div>
                    <div class="ev-proof-v5">证明内容：{format_proof_html(ev['proof'])}</div>
                    <div class="dual-img-container-v5">
                        <div class="dual-img-col-v5">
                            <img class="ev-img-v5" src="{img1['path']}">
                        </div>
                        <div class="dual-img-col-v5">
                            <img class="ev-img-v5" src="{img2['path']}">
                        </div>
                    </div>
                </div>
            """
            
        elif p_type == 'single_wide':
            ev = evs[0]
            img_data = ev['images'][0]
            page_html += f"""
                <div class="col-v5">
                    <div class="ev-title-v5">证据{ev['num']}：{html.escape(ev['title'])}</div>
                    <div class="ev-proof-v5">证明内容：{format_proof_html(ev['proof'])}</div>
                    <div class="wide-img-container-v5">
                        <img class="wide-img-v5" src="{img_data['path']}">
                    </div>
                </div>
            """
            
        elif p_type == 'single_tall_left':
            ev = evs[0]
            img_data = ev['images'][0]
            page_html += f"""
                <div class="single-left-container-v5">
                    <div class="col-v5">
                        <div class="ev-title-v5">证据{ev['num']}：{html.escape(ev['title'])}</div>
                        <div class="ev-proof-v5">证明内容：{format_proof_html(ev['proof'])}</div>
                        <div class="ev-img-box-v5">
                            <img class="ev-img-v5" src="{img_data['path']}">
                        </div>
                    </div>
                    <div><!-- 右侧大方留白，绝不跨目的混排 --></div>
                </div>
            """
            
        page_html += """
            </div>
        </div>
        """
        html_pages.append(page_html)
        
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>民事诉讼证据册</title>
    <style>
    {css_content}
    </style>
</head>
<body>
    {''.join(html_pages)}
</body>
</html>
"""
    return full_html

def render_chromium_pdf(html_path, out_pdf_path):
    print("=" * 60)
    print("【第六阶段】启动 Chromium 无头引擎进行高保真 PDF 渲染...")
    cmd = [
        'chromium',
        '--headless',
        '--disable-gpu',
        '--no-sandbox',
        '--allow-file-access-from-files',
        '--no-pdf-header-footer',
        f'--print-to-pdf={out_pdf_path}',
        html_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Chromium 渲染失败: {res.stderr}")
        sys.exit(1)
    if not os.path.exists(out_pdf_path):
        print(f"❌ 未检测到生成的 PDF 文件: {out_pdf_path}")
        sys.exit(1)
        
    size_mb = os.path.getsize(out_pdf_path) / 1024 / 1024
    print(f"✅ Chromium PDF 渲染成功！原始 PDF 大小: {size_mb:.2f} MB")
    print("=" * 60)

def assemble_final_pdf(body_pdf_path, final_pdf_path, sections, pages, evidence_page_map, purpose_page_ranges, appendix_ranges):
    """
    第七阶段：顺延合并外部裁定书与流水、全册矢量统一打码与法庭书签导航
    """
    print("=" * 60)
    print("【第七阶段】无缝顺延合并外部附录、矢量打码与全案书签注入...")
    
    # 1. 打开正文 PDF (包含目录第 1 页 + 正文 41 页 = 42 页)
    main_doc = fitz.open(body_pdf_path)
    body_count = len(main_doc)
    print(f"   * 正文 PDF 页数: {body_count} 页 (P1-P{body_count})")
    
    # 2. 合并证据二：民事裁定书 (2 页)
    if os.path.exists(COURT_RULING_PDF):
        ruling_doc = fitz.open(COURT_RULING_PDF)
        main_doc.insert_pdf(ruling_doc)
        print(f"   * 追加证据二《民事裁定书》: {len(ruling_doc)} 页")
        ruling_doc.close()
    else:
        print("   ⚠️ 未找到民事裁定书.pdf")
        
    # 3. 合并证据三：信用卡流水账单 (从 v5 提取后 10 页)
    if os.path.exists(V5_PDF):
        v5_doc = fitz.open(V5_PDF)
        # v5 的后 10 页是信用卡流水凭证 (46-55 索引)
        v5_bill_pages = range(46, len(v5_doc))
        main_doc.insert_pdf(v5_doc, from_page=46, to_page=len(v5_doc)-1)
        print(f"   * 追加证据三《信用卡账单及流水凭证》: {len(v5_bill_pages)} 页")
        v5_doc.close()
    else:
        print("   ⚠️ 未找到 v5 信用卡流水页")
        
    total_pages = len(main_doc)
    print(f"   * 全案合并最终总页数: {total_pages} 页")
    
    # 4. 构建全案多级书签 (TOC)
    toc = []
    toc.append([1, "原告提交的《证据目录》", 1])
    toc.append([1, "证据一：微信聊天记录及被告自述材料汇总 (P2-P42)", 2])
    
    for s in sections:
        p_num = s['p_num_str']
        p_title = s['p_title']
        prange = purpose_page_ranges[p_num]
        toc.append([2, f"证明目的{p_num}：{p_title} (P{prange[0]}-P{prange[1]})", prange[0]])
        for ev in s['evidences']:
            ev_p = evidence_page_map[ev['num']]
            toc.append([3, f"证据{ev['num']}：{ev['title']}", ev_p])
            
    toc.append([1, f"证据二：《民事裁定书》（撤诉） (P{appendix_ranges['ev2'][0]}-P{appendix_ranges['ev2'][1]})", appendix_ranges['ev2'][0]])
    toc.append([1, f"证据三：信用卡账单及扣款流水凭证 (P{appendix_ranges['ev3'][0]}-P{appendix_ranges['ev3'][1]})", appendix_ranges['ev3'][0]])
    
    main_doc.set_toc(toc)
    
    # 5. 全册 54 页统一定位矢量页码：第 X 页 / 共 54 页
    footer_color = (0.15, 0.15, 0.15)
    for i, page in enumerate(main_doc):
        page_num = i + 1
        footer_text = f"第 {page_num} 页 / 共 {total_pages} 页"
        rect = fitz.Rect(0, 814, 595.28, 832)
        page.insert_textbox(
            rect,
            footer_text,
            fontsize=10.0,
            fontname="china-s",
            color=footer_color,
            align=fitz.TEXT_ALIGN_CENTER
        )
        
    main_doc.save(final_pdf_path, garbage=4, deflate=True)
    main_doc.close()
    
    final_size_mb = os.path.getsize(final_pdf_path) / 1024 / 1024
    print(f"✅ 全案高保真合并与矢量页码注入完成！")
    print(f"   * 交付文件: {final_pdf_path}")
    print(f"   * 交付总页数: {total_pages} 页")
    print(f"   * 交付大小: {final_size_mb:.2f} MB")
    print("=" * 60)

def main():
    md_text, img_map = stage_1_audit(MD_PATH, IMG_DIR)
    sections = parse_markdown_and_images(md_text, img_map, IMG_DIR)
    pages, evidence_page_map, purpose_page_ranges = plan_pages(sections)
    
    ev1_end_page = max(evidence_page_map.values())
    ev2_start = ev1_end_page + 1
    ev2_end = ev2_start + 1 # 裁定书 2 页: 43-44
    ev3_start = ev2_end + 1
    ev3_end = ev3_start + 9 # 流水凭证 10 页: 45-54
    
    appendix_ranges = {
        'ev2': (ev2_start, ev2_end),
        'ev3': (ev3_start, ev3_end)
    }
    
    print(f"【精确页码计算】证据一: P2-P{ev1_end_page} | 证据二: P{ev2_start}-P{ev2_end} | 证据三: P{ev3_start}-P{ev3_end}")
    for p_num, r in purpose_page_ranges.items():
        print(f"   * 证明目的 {p_num}: P{r[0]}-P{r[1]}")
        
    html_content = generate_html(sections, pages, evidence_page_map, purpose_page_ranges, appendix_ranges)
    with open(TMP_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ 临时 HTML 构建完成: {TMP_HTML_PATH}")
    
    render_chromium_pdf(TMP_HTML_PATH, TMP_PDF_BODY)
    assemble_final_pdf(TMP_PDF_BODY, OUT_PDF_PATH, sections, pages, evidence_page_map, purpose_page_ranges, appendix_ranges)
    
    if os.path.exists(TMP_PDF_BODY):
        os.remove(TMP_PDF_BODY)
    if os.path.exists(TMP_HTML_PATH):
        os.remove(TMP_HTML_PATH)
        
    print("\n🎉 全案极简高保真呈堂级 PDF 证据册（含精确多证明目的目录映射）生成完毕！")

if __name__ == '__main__':
    main()
