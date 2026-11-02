from pathlib import Path
from config import CFG

print('=== ДИАГНОСТИКА ===')
print(f'BASE_DIR: {CFG.db_path.parent}')
print(f'webapp_dir: {CFG.webapp_dir}')
print(f'webapp_url: {CFG.webapp_url}')
print(f'Папка webapp существует: {CFG.webapp_dir.exists()}')
if CFG.webapp_dir.exists():
    files = list(CFG.webapp_dir.glob('*'))
    print(f'Файлы в webapp: {[f.name for f in files]}')
else:
    print('Папка webapp НЕ существует!')

app_html = CFG.webapp_dir / "app.html"
print(f'Файл app.html существует: {app_html.exists()}')
if app_html.exists():
    print(f'Размер app.html: {app_html.stat().st_size} байт')
