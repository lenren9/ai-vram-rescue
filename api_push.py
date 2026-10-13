import os, sys, json, base64, io, urllib.request, urllib.error

REPO = r'D:\deepseek-harness\default-workspace\_repo2'
TOK = (open(os.path.join(os.environ['USERPROFILE'], '.git-credentials'), encoding='utf-8')
       .read().strip().split(':')[2].replace('@github.com', ''))
USER, REPO_NAME, BRANCH = 'lenren9', 'windows-ai-toolkit', 'main'
API = f'https://api.github.com/repos/{USER}/{REPO_NAME}/contents'
HDRS = {'Authorization': f'Bearer {TOK}', 'User-Agent': 'dsh-upload',
        'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'}


def req(method, url, data=None, timeout=90):
    body = json.dumps(data).encode('utf-8') if data is not None else None
    r = urllib.request.Request(url, data=body, headers=HDRS, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return None, str(e)


def push(rel, ap):
    raw = open(ap, 'rb').read()
    content = base64.b64encode(raw).decode('ascii')
    url = f'{API}/{rel.replace(chr(92), "/")}'
    st, info = req('GET', url + f'?ref={BRANCH}')
    payload = {'message': f'Update {rel}', 'content': content, 'branch': BRANCH}
    if st == 200 and isinstance(info, dict) and 'sha' in info:
        payload['sha'] = info['sha']
    else:
        payload['message'] = f'Add {rel}'
    st2, res2 = req('PUT', url, payload)
    ok = st2 in (200, 201)
    url2 = res2.get('content', {}).get('html_url') if isinstance(res2, dict) else str(res2)[:100]
    return ok, st2, url2


files = []
for root, dirs, fs in os.walk(REPO):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for fn in fs:
        ap = os.path.join(root, fn)
        rel = os.path.relpath(ap, REPO).replace('\\', '/')
        files.append((rel, ap))

print(f'共 {len(files)} 个文件\n')
ok_n = 0
for rel, ap in sorted(files):
    ok, st, u = push(rel, ap)
    print(f'  [{"OK " if ok else "FAIL"}] {st}  {rel:46s} {os.path.getsize(ap)/1024:6.1f} KB')
    ok_n += bool(ok)
print(f'\n成功 {ok_n}/{len(files)}')
