#!/bin/bash
# 自动更新 GitHub 热门项目数据
# 1. 生成中文简介（intros.json）
# 2. 注入到 HTML
# 3. 复制到 D 盘，更新桌面快捷方式

PROJECT_DIR=/home/dww_linux/projects/github-stats
TARGET_DIR="/mnt/d/github-trending"
DESKTOP_DIR="/mnt/c/Users/dww/Desktop"
HTML_NAME="GitHub热门项目排行榜.html"
LOG_FILE=/tmp/trending-update.log

cd "$PROJECT_DIR"

# 加载 API 凭据
source /home/dww_linux/.bashrc 2>/dev/null

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始更新..."

# 1. 生成中文简介（失败也继续，用旧缓存）
python3 generate_intros.py >> "$LOG_FILE" 2>&1 && {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 简介生成完成" >> "$LOG_FILE"
} || {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 简介生成失败，使用已有缓存" >> "$LOG_FILE"
}

# 2. 注入 intros.json 到 HTML
python3 -c "
import json, re

with open('intros.json', 'r', encoding='utf-8') as f:
    intros = json.load(f)

with open('trending.html', 'r', encoding='utf-8') as f:
    html = f.read()

json_str = json.dumps(intros, ensure_ascii=False)
new_script = f'<script id=\"intros-data\" type=\"application/json\">\n{json_str}\n</script>'
html = re.sub(
    r'<script id=\"intros-data\" type=\"application/json\">.*?</script>',
    new_script,
    html,
    flags=re.DOTALL
)

with open('trending.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('intros 已注入 HTML')
"

# 3. 确保 D 盘目标目录存在
mkdir -p "$TARGET_DIR"

# 4. 复制到 D 盘
cp trending.html "$TARGET_DIR/$HTML_NAME"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已复制到 D:\\github-trending\\" >> "$LOG_FILE"

# 5. 创建/更新桌面快捷方式（指向 D 盘文件）
powershell.exe -Command "
\$WshShell = New-Object -ComObject WScript.Shell
\$Shortcut = \$WshShell.CreateShortcut('C:\\Users\\dww\\Desktop\\GitHub热门项目.lnk')
\$Shortcut.TargetPath = 'D:\\github-trending\\GitHub热门项目排行榜.html'
\$Shortcut.Save()
" 2>/dev/null

# 删除旧的桌面副本和 .url（现在用 .lnk 快捷方式代替）
rm -f "$DESKTOP_DIR/GitHub热门项目排行榜.html" \
      "$DESKTOP_DIR/intros.json" \
      "$DESKTOP_DIR/GitHub热门项目排行榜.url"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 更新成功 ✓" >> "$LOG_FILE"
echo "完成：D:\\github-trending\\GitHub热门项目排行榜.html"
