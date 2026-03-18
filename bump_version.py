import os
import re

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.py')

def bump(m):
    p = m.group(1).split('.')
    p[-1] = str(int(p[-1]) + 1)
    return 'APP_VERSION = "' + '.'.join(p) + '"'

def main():
    if not os.path.exists(CONFIG_FILE):
        return
        
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    new_content = re.sub(r'APP_VERSION\s*=\s*"([^"]+)"', bump, content)
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)

if __name__ == "__main__":
    main()
