import re

def parse_class_tokens(classes_str):
    if not classes_str or not classes_str.strip():
        return []
    
    # Pattern to match Grade number followed by class letters
    # E.g. '8ABCD9ABCD' -> ('8', 'ABCD'), ('9', 'ABCD')
    # E.g. '11I12EFGH' -> ('11', 'I'), ('12', 'EFGH')
    # E.g. '10H12BFGHI' -> ('10', 'H'), ('12', 'BFGHI')
    # E.g. '7E11AE' -> ('7', 'E'), ('11', 'AE')
    pattern = re.compile(r'(\d+)([A-Za-z]+)')
    matches = pattern.findall(classes_str)
    
    result = []
    for grade_num, letters in matches:
        for letter in letters.upper():
            result.append(f"{grade_num}{letter}")
    return result

test_cases = [
    ('7ABCD', ['7A', '7B', '7C', '7D']),
    ('8ABCD9ABCD', ['8A', '8B', '8C', '8D', '9A', '9B', '9C', '9D']),
    ('11I12EFGH', ['11I', '12E', '12F', '12G', '12H']),
    ('10H12BFGHI', ['10H', '12B', '12F', '12G', '12H', '12I']),
    ('7E11AE', ['7E', '11A', '11E']),
    ('10A12CDI', ['10A', '12C', '12D', '12I']),
]

for s, exp in test_cases:
    res = parse_class_tokens(s)
    print(f"Input: {s:15s} => Parsed: {res} (Matches Expected: {res == exp})")
