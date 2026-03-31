import os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Busca o corpo da função hideEvent e injeta o wait
    old_text = 'self._timer.stop()\n        super().hideEvent(event)'
    new_text = 'self._timer.stop()\n        for attr in ("_worker", "_admin_check_worker", "_status_worker"):\n            w = getattr(self, attr, None)\n            if w and w.isRunning():\n                w.wait(200)\n        super().hideEvent(event)'
    
    # Tenta com \r\n também
    if old_text not in content:
        old_text = 'self._timer.stop()\r\n        super().hideEvent(event)'
        new_text = 'self._timer.stop()\r\n        for attr in ("_worker", "_admin_check_worker", "_status_worker"):\r\n            w = getattr(self, attr, None)\r\n            if w and w.isRunning():\r\n                w.wait(200)\r\n        super().hideEvent(event)'

    if old_text in content:
        new_content = content.replace(old_text, new_text)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"SUCESSO: {os.path.basename(path)} foi corrigido.")
    else:
        print(f"ERRO: Nao foi possivel localizar o local exato no arquivo {os.path.basename(path)}.")

# Executa para o Portable
fix_file('c:/Dio/Outros/Python/V5.0/futura-setup/ui/page_fb_portable.py')
