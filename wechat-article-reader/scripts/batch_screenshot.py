import subprocess, json, time, base64, os, re

def btool(tool, args):
    args_str = json.dumps(args, ensure_ascii=False)
    r = subprocess.run(['mavis.cmd', 'browser', 'tool', tool, args_str], capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except:
        return {'raw': r.stdout}

articles = [
    ('01', 'https://mp.weixin.qq.com/s/OImHo6EXyK4TIqB5esF3PA', '只记住利他思维是做不好小红书的'),
    ('02', 'https://mp.weixin.qq.com/s/bVDjuJ0ezbhgEAnQleaUgw', '别再怀疑被限流了，你的小红书号大概率没毛病'),
    ('04', 'https://mp.weixin.qq.com/s/6lHFvubgBGWLMvWiOqYuMA', '你还在苦恼小眼睛不过百吗'),
    ('05', 'https://mp.weixin.qq.com/s/CI1DtljlnAa8UETgJw12Hg', '经常收到很多新手小白的问题'),
    ('06', 'https://mp.weixin.qq.com/s/dp1lNxFDpdQQhnqmHaac2A', '想做小红书第一件事就是找对标'),
    ('09', 'https://mp.weixin.qq.com/s/6GLGUWCRnoklJY5Gxva0lA', '做这么多的账号诊断，看过这么多账号之后'),
    ('13', 'https://mp.weixin.qq.com/s/Nfk3A09UiAdLDUAvlg8GHw', '为什么你连续日更30条笔记还是没有流量'),
]

for num, url, title in articles:
    print(f'\n[{num}] Opening: {title}')
    r = btool('open_tab', {'url': url, 'active': True})
    tab = r.get('tabId')
    if not tab:
        print(f'  Failed to open tab')
        continue
    print(f'  TabId: {tab}')
    time.sleep(5)

    btool('claim_tab', {'tabId': tab, 'force': True})
    time.sleep(2)

    img_paths = []
    for i in range(6):
        ss = btool('screenshot', {'tabId': tab})
        data = ss.get('content', '')
        if data:
            b64 = data.split(',', 1)[1] if ',' in data else data
            img_data = base64.b64decode(b64 + '==')
            fname = f'articles/ss_{num}_{i}.png'
            with open(fname, 'wb') as f:
                f.write(img_data)
            img_paths.append(os.path.abspath(fname))
            print(f'  Screenshot {i+1}: {len(img_data)} bytes')
        if i < 5:
            btool('scroll', {'tabId': tab, 'y': 600})
            time.sleep(2)

    # Close tab
    btool('close_tab', {'tabId': tab})
    print(f'  Captured {len(img_paths)} screenshots')