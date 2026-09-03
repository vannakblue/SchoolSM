import re

with open(r'e:\SchoolSM\templates\academics\daily_reports.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract script blocks
scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
print(f"Found {len(scripts)} script block(s).")

for idx, s in enumerate(scripts, 1):
    # Remove django tags for basic brace matching
    cleaned = re.sub(r'\{%.*?%\}', '""', s)
    cleaned = re.sub(r'\{\{.*?\}\}', '""', cleaned)
    
    open_curly = cleaned.count('{')
    close_curly = cleaned.count('}')
    open_paren = cleaned.count('(')
    close_paren = cleaned.count(')')
    open_bracket = cleaned.count('[')
    close_bracket = cleaned.count(']')
    
    print(f"Script #{idx}:")
    print(f"  Curlys: {open_curly} open, {close_curly} close (Diff: {open_curly - close_curly})")
    print(f"  Parens: {open_paren} open, {close_paren} close (Diff: {open_paren - close_paren})")
    print(f"  Brackets: {open_bracket} open, {close_bracket} close (Diff: {open_bracket - close_bracket})")
    
    if open_curly == close_curly and open_paren == close_paren and open_bracket == close_bracket:
        print("  -> ALL BRACKETS MATCHED PERFECTLY!")
    else:
        print("  -> MISMATCH DETECTED!")
