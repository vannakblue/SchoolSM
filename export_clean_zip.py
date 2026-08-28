import os
import zipfile
import datetime

def create_clean_backup():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backups_dir = os.path.join(base_dir, 'backups')
    os.makedirs(backups_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    zip_name = f"SchoolSM_Clean_Backup_{timestamp}.zip"
    zip_path = os.path.join(backups_dir, zip_name)

    EXCLUDE_DIRS = {'.venv', 'venv', 'env', '__pycache__', '.idea', '.vscode', 'staticfiles', 'node_modules'}
    EXCLUDE_EXTS = {'.pyc', '.pyo', '.pyd', '.tmp', '.log'}

    print(f"[1/2] Creating clean project backup: {zip_name} ...")
    file_count = 0

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.git') and d != 'backups']
            
            for file in files:
                if file.startswith('~$') or file.endswith('.tmp'):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                
                zipf.write(full_path, rel_path)
                file_count += 1

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[2/2] [SUCCESS] Clean backup created successfully!")
    print(f"      - File path: {zip_path}")
    print(f"      - Total files archived: {file_count}")
    print(f"      - Archive size: {size_mb:.2f} MB (Extremely clean & lightweight!)")
    return zip_path

if __name__ == '__main__':
    create_clean_backup()
