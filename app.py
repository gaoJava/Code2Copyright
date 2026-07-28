from __future__ import annotations

import json
import os
import struct
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from generator import export_docx, scan_project


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>软著源代码文档生成器</title>
  <style>
    *{box-sizing:border-box} body{margin:0;background:#f5f7fb;color:#172033;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}
    .page{max-width:900px;margin:52px auto;padding:0 20px}.card{background:#fff;border-radius:18px;
    padding:34px;box-shadow:0 14px 44px rgba(35,55,90,.09)}h1{font-size:28px;margin:0 0 8px}
    .lead{color:#687386;margin:0 0 30px}.field{margin:18px 0}label.title{display:block;
    font-weight:650;margin-bottom:9px}input[type=text]{width:100%;border:1px solid #d7dce5;
    border-radius:9px;padding:12px 13px;font-size:15px;outline:none}input[type=text]:focus{
    border-color:#3578e5;box-shadow:0 0 0 3px #3578e51b}.picker{border:2px dashed #cbd3e0;
    border-radius:12px;padding:24px;text-align:center;background:#fafbfe}.picker input{max-width:100%}
    .radios{display:grid;gap:10px;color:#344055}.hint,.status{font-size:14px;color:#778196}
    .modules{display:flex;gap:10px}.modules select{flex:1;min-height:116px;border:1px solid #d7dce5;
    border-radius:9px;padding:6px;font-size:14px}.module-actions{display:grid;align-content:center;gap:7px}
    .module-actions button{background:#eef3fb;color:#2b5da8;padding:8px 12px;font-size:14px}
    .status{margin-top:13px;min-height:21px}.status.ok{color:#18864b}.status.err{color:#c73535}
    button{border:0;border-radius:10px;background:#246be0;color:white;font-size:16px;font-weight:650;
    padding:13px 25px;cursor:pointer}button:disabled{background:#aeb9cb;cursor:not-allowed}
    .actions{display:flex;justify-content:flex-end;margin-top:26px}
  </style>
</head>
<body><main class="page"><section class="card">
  <h1>软著源代码文档生成器</h1>
  <p class="lead">选择整个项目目录，自动整理源码并导出 Word 文档。</p>
  <div class="field">
    <label class="title" for="name">软件名称</label>
    <input id="name" type="text" placeholder="例如：智能数据管理系统 V1.0">
  </div>
  <div class="field">
    <label class="title">源码项目目录</label>
    <div class="picker"><input id="folder" type="file" webkitdirectory directory multiple></div>
    <div id="status" class="status">尚未选择目录</div>
  </div>
  <div class="field">
    <label class="title">导出范围</label>
    <div class="radios">
      <label><input name="mode" type="radio" value="first_last" checked>
        前 30 页＋后 30 页（不足 60 页时自动全部导出）</label>
      <label><input name="mode" type="radio" value="all"> 全部源码</label>
    </div>
  </div>
  <div class="field">
    <label class="title">模块拼接顺序</label>
    <div class="modules">
      <select id="modules" size="5"></select>
      <div class="module-actions">
        <button type="button" id="up">上移 ↑</button>
        <button type="button" id="down">下移 ↓</button>
      </div>
    </div>
    <div class="hint">列表顶部模块进入源码前段，列表底部模块进入源码后段。</div>
  </div>
  <p class="hint">支持 Python、Java、Vue、JavaScript、C/C++、Go、SQL 等；自动过滤
    .git、node_modules、venv、build、dist。</p>
  <div class="actions"><button id="export" disabled>导出 Word 文档</button></div>
</section></main>
<script>
const folder=document.querySelector('#folder'), statusEl=document.querySelector('#status');
const button=document.querySelector('#export'), nameEl=document.querySelector('#name');
const modulesEl=document.querySelector('#modules');
const ignored=new Set(['.git','.svn','.hg','.idea','.vscode','__pycache__','node_modules',
  'venv','.venv','env','.env','build','dist','target','out','coverage','.next','.nuxt',
  '.cache','vendor']);
const extensions=new Set(['py','pyw','java','kt','kts','vue','js','jsx','ts','tsx','mjs',
  'cjs','c','h','cc','cpp','cxx','hpp','hh','go','sql','html','htm','css','scss','less',
  'php','cs','rs','rb','swift','scala','sh','yaml','yml','xml','json','properties','gradle']);
function accepted(file){
  const parts=file.webkitRelativePath.split('/');
  if(parts.some(p=>ignored.has(p))) return false;
  const n=file.name.toLowerCase(), ext=n.includes('.')?n.split('.').pop():'';
  return extensions.has(ext)&&!n.endsWith('.min.js')&&!n.endsWith('.min.css')&&!n.endsWith('.map');
}
folder.addEventListener('change',()=>{
  const files=[...folder.files].filter(accepted);
  const modules=[];
  for(const file of files){
    const parts=file.webkitRelativePath.split('/');
    const module=parts.length>2?parts[1]:'.';
    if(!modules.includes(module))modules.push(module);
  }
  modules.sort((a,b)=>a.localeCompare(b,'zh-CN'));
  modulesEl.replaceChildren(...modules.map(module=>{
    const option=document.createElement('option');
    option.value=module;option.textContent=module==='.'?'（项目根目录文件）':module;
    return option;
  }));
  if(modulesEl.options.length)modulesEl.selectedIndex=0;
  if(folder.files.length&& !nameEl.value) nameEl.value=folder.files[0].webkitRelativePath.split('/')[0];
  statusEl.className='status '+(files.length?'ok':'err');
  statusEl.textContent=files.length?`已选择 ${files.length} 个源码文件（共检查 ${folder.files.length} 个文件）`
    :'所选目录中没有发现支持的源码文件';
  button.disabled=!files.length;
});
function moveModule(offset){
  const index=modulesEl.selectedIndex, target=index+offset;
  if(index<0||target<0||target>=modulesEl.options.length)return;
  const selected=modulesEl.options[index];
  if(offset<0)modulesEl.insertBefore(selected,modulesEl.options[target]);
  else modulesEl.insertBefore(modulesEl.options[target],selected);
  modulesEl.selectedIndex=target;
}
document.querySelector('#up').addEventListener('click',()=>moveModule(-1));
document.querySelector('#down').addEventListener('click',()=>moveModule(1));
button.addEventListener('click',async()=>{
  const files=[...folder.files].filter(accepted);
  if(!files.length)return;
  button.disabled=true; button.textContent='正在生成…';
  statusEl.className='status'; statusEl.textContent='正在上传并整理源码，请稍候…';
  // 将所有源码作为一个二进制流发送，避免大量 multipart 临时文件耗尽系统句柄。
  const parts=[new TextEncoder().encode('C2C1')];
  const encoder=new TextEncoder();
  for(const file of files){
    const path=encoder.encode(file.webkitRelativePath);
    const header=new ArrayBuffer(12), view=new DataView(header);
    view.setUint32(0,path.byteLength);
    view.setBigUint64(4,BigInt(file.size));
    parts.push(header,path,file);
  }
  parts.push(new Uint8Array(4));
  const payload=new Blob(parts,{type:'application/octet-stream'});
  try{
    const response=await fetch('/generate',{
      method:'POST',
      headers:{
        'X-Software-Name':encodeURIComponent(nameEl.value.trim()||'软件'),
        'X-Export-Mode':document.querySelector('input[name=mode]:checked').value,
        'X-Module-Order':encodeURIComponent(JSON.stringify([...modulesEl.options].map(o=>o.value)))
      },
      body:payload
    });
    if(!response.ok)throw new Error(await response.text());
    const blob=await response.blob(), url=URL.createObjectURL(blob), a=document.createElement('a');
    const cd=response.headers.get('Content-Disposition')||'';
    const match=cd.match(/filename\*=UTF-8''([^;]+)/);
    a.href=url;a.download=match?decodeURIComponent(match[1]):'源代码.docx';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    statusEl.className='status ok';statusEl.textContent='生成完成，Word 文档已开始下载。';
  }catch(err){statusEl.className='status err';statusEl.textContent='生成失败：'+err.message}
  finally{button.disabled=false;button.textContent='导出 Word 文档'}
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/generate":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_error(413, "项目文件总大小不能超过 2 GB")
            return
        try:
            self._generate_stream(length)
        except Exception as exc:
            body = str(exc).encode("utf-8", errors="replace")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _read_exact(self, size: int) -> bytes:
        chunks = []
        remaining = size
        while remaining:
            chunk = self.rfile.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("源码传输中断，请重新导出")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _copy_exact(self, target, size: int) -> None:
        remaining = size
        while remaining:
            chunk = self.rfile.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("源码传输中断，请重新导出")
            target.write(chunk)
            remaining -= len(chunk)

    def _generate_stream(self, length: int) -> None:
        software_name = unquote(self.headers.get("X-Software-Name", "软件")).strip()
        mode = self.headers.get("X-Export-Mode", "first_last")
        module_order_raw = unquote(self.headers.get("X-Module-Order", "[]"))
        module_order = json.loads(module_order_raw)
        if not isinstance(module_order, list) or not all(
            isinstance(item, str) for item in module_order
        ):
            raise ValueError("模块顺序无效")
        if mode not in ("first_last", "all"):
            raise ValueError("导出模式无效")
        if self._read_exact(4) != b"C2C1":
            raise ValueError("源码数据格式无效，请刷新页面后重试")

        with tempfile.TemporaryDirectory(prefix="code2copyright-") as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            file_count = 0
            while True:
                path_length = struct.unpack(">I", self._read_exact(4))[0]
                if path_length == 0:
                    break
                if path_length > 16384:
                    raise ValueError("源码文件路径过长")
                file_size = struct.unpack(">Q", self._read_exact(8))[0]
                if file_size > MAX_UPLOAD_BYTES:
                    raise ValueError("单个源码文件不能超过 2 GB")
                relative = Path(self._read_exact(path_length).decode("utf-8"))
                safe_parts = [p for p in relative.parts if p not in ("", ".", "..", "/")]
                # 浏览器路径的第一段是所选项目目录名，去掉它以免多嵌套一层。
                if len(safe_parts) > 1:
                    safe_parts = safe_parts[1:]
                if not safe_parts:
                    raise ValueError("发现无效的源码路径")
                target = root.joinpath(*safe_parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as output_file:
                    self._copy_exact(output_file, file_size)
                file_count += 1

            if not file_count:
                raise ValueError("没有收到源码文件")

            result = scan_project(root, module_order)
            if not result.lines:
                raise ValueError("没有发现可导出的源码")
            output = Path(tmp) / "source.docx"
            export_docx(result, output, software_name, mode)
            body = output.read_bytes()

        filename = "".join(c for c in software_name if c not in r'\/:*?"<>|').strip() or "软件"
        from urllib.parse import quote
        encoded_name = quote(filename + "_源代码.docx")
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + encoded_name)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print("[软著生成器] " + fmt % args)


def main() -> None:
    port = int(os.environ.get("CODE2COPYRIGHT_PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer((HOST, port), Handler)
    url = "http://{}:{}/".format(HOST, port)
    print("软著源代码文档生成器已启动：{}".format(url))
    print("关闭工具请回到终端按 Control+C")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n工具已关闭")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
