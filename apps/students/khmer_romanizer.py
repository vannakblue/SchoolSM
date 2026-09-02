"""
Khmer-to-Latin Romanization Engine for SchoolSM.
Provides highly accurate phonetic transliteration for Khmer names adhering to standard
MoEYS (Ministry of Education, Youth and Sport) & UNGEGN Cambodian naming standards.
"""

import re
from typing import List, Dict, Optional

# Comprehensive Dictionary of Khmer Surnames, Given Names, and Syllables
KHMER_NAME_DICTIONARY: Dict[str, str] = {
    # Common Surnames / Family Names (ត្រកូល)
    'សុខ': 'Sok', 'ហេង': 'Heng', 'សេង': 'Seng', 'គង់': 'Kong', 'រស់': 'Ros', 'លី': 'Ly',
    'ចាន់': 'Chan', 'ឡុង': 'Long', 'កែវ': 'Keo', 'ម៉ៅ': 'Mao', 'ជា': 'Chea', 'យិន': 'Yin',
    'អ៊ុក': 'Ouk', 'ស៊ូ': 'Sou', 'ឈាង': 'Chheang', 'មាស': 'Meas', 'វ៉ាន់': 'Van', 'នួន': 'Nuon',
    'ឌិត': 'Dith', 'ប៉ែន': 'Pen', 'អ៊ុំ': 'Oum', 'ស៊ិន': 'Sin', 'ពេជ្រ': 'Pech', 'សម្បត្តិ': 'Sambath',
    'ឃួន': 'Khuon', 'អ៊ុច': 'Ouch', 'ទេព': 'Tep', 'រិន': 'Rin', 'គឹម': 'Kim', 'ឃឹម': 'Khim',
    'ស៊ុន': 'Sun', 'អ៊ឹង': 'Eang', 'ឡេង': 'Leng', 'អេង': 'Eng', 'អ៊ិន': 'In', 'សន': 'Son',
    'យន់': 'Yon', 'ខៀវ': 'Khiev', 'ប្រាក់': 'Prak', 'ទូច': 'Touch', 'ទិត': 'Tith', 'ទិន': 'Tin',
    'ទុន': 'Tun', 'ឌី': 'Dy', 'ដួង': 'Duong', 'ឈួន': 'Chhuon', 'ឆាយ': 'Chhay', 'ឆេង': 'Chheng',
    'ចេង': 'Cheng', 'ងួន': 'Nguon', 'ខឹម': 'Khim', 'ខុត': 'Khut', 'ឃាង': 'Kheang', 'កង': 'Kang',
    'កុសល': 'Kosal', 'កឿន': 'Koeun', 'គាន': 'Kean', 'គ្រីន': 'Krin', 'ញ៉ែម': 'Nhem', 'ញឹក': 'Nhek',
    'តាំង': 'Tang', 'តូច': 'Touch', 'ថោង': 'Thaong', 'ផន': 'Phorn', 'ផល': 'Phal', 'ផាត់': 'Phat',
    'ផេង': 'Pheng', 'ពៅ': 'Pov', 'ភោគ': 'Phok', 'មុំ': 'Mom', 'មូល': 'Moul', 'មៀច': 'Miech',
    'ម៉ម': 'Morm', 'យូ': 'You', 'រិទ្ធ': 'Rith', 'លន់': 'Lon', 'លឿង': 'Loeung', 'វណ្ណៈ': 'Vannak',
    'សាន': 'San', 'ស៊ា': 'Sea', 'ស្រ៊ុន': 'Srun', 'ហុង': 'Hong', 'ហួត': 'Huot', 'ហៀង': 'Heang',
    'ហ៊ឺ': 'Heu', 'ហ៊ូ': 'Hou', 'អាន': 'An', 'អៀ': 'Iea', 'អ៊ុយ': 'Uy', 'ឯក': 'Ek',
    'យ៉ាន់': 'Yann', 'យ៉ុន': 'Yon', 'យ៉ន': 'Yorn', 'យ៉ាង': 'Yang', 'យ៉េន': 'Yen', 'សាក់': 'Sak',
    'សោម': 'Som', 'ស៊ុំ': 'Sum', 'ស៊ុយ': 'Suy', 'ប៉ាង': 'Pang', 'ប៉ាល់': 'Pal', 'ពិន': 'Pin',
    'ខន': 'Khorn', 'ខា': 'Kha', 'កេត': 'Ket', 'សាត': 'Sat', 'សាន់': 'San', 'ខាន់': 'Khan',

    # Compound & Popular Given Names (ឈ្មោះខ្លួន)
    'សុជាតា': 'Socheata', 'ចំរើន': 'Chamroeun', 'ពិសី': 'Pisey', 'បញ្ញា': 'Panha', 'រតនា': 'Rattana',
    'មករា': 'Makara', 'រស្មី': 'Reaksmey', 'ចរិយា': 'Chariya', 'រចនា': 'Rachana', 'សីហា': 'Seyha',
    'រក្សា': 'Raksa', 'គឹមសាន': 'Kimsan', 'សោភា': 'Sophea', 'វិចិត្រ': 'Vichetr', 'ចិន្តា': 'Chinda',
    'សុធី': 'Sothey', 'សុធារ៉ា': 'Sotheara', 'សុផាត': 'Sophat', 'សុភ័ក្រ': 'Sopheak', 'សុភារៈ': 'Sophearak',
    'សុផា': 'Sopha', 'សុផាន': 'Sophan', 'សុផារិទ្ធ': 'Sopharith', 'សុផន': 'Sophon', 'សុមនី': 'Somony',
    'សុម៉ាឡា': 'Somala', 'សុសៅគន្ធ': 'Sosaokunth', 'សូរីយា': 'Soriya', 'សោម៉នវីរៈ': 'Somonvirak',
    'សុវណ្ណ': 'Sovann', 'សុវណ្ណារ៉ា': 'Sovannara', 'សុវណ្ណារិទ្ធ': 'Sovannarith', 'សុវណ្ណថន': 'Sovannthon',
    'សុវណ្ណមុនី': 'Sovannmony', 'សុវណ្ណលីដា': 'Sovannlyda', 'សុខខេង': 'Sokkheng', 'សុខឃៀង': 'Sokkheang',
    'សុខចាន់': 'Sokchan', 'សុខម៉េត': 'Sokmet', 'សុខា': 'Sokha', 'សុខុម': 'Sokhom', 'សុគង់': 'Sokong',
    'សុគន្ធា': 'Sokunthea', 'សុគន្ធារី': 'Sokuntheary', 'សុដានី': 'Sodany', 'សុទ្ធ': 'Soth',
    'វិសាល': 'Visal', 'វីរៈ': 'Virak', 'វាសនា': 'Veasna', 'វឌ្ឍនៈ': 'Vattanak', 'វឌ្ឍនា': 'Vattana',
    'វឌ្ឍនី': 'Vattany', 'រិទ្ធី': 'Rithy', 'រិទ្ធីយ៉ា': 'Rithiya', 'រដ្ឋា': 'Ratha', 'រស្មីច័ន្ទ': 'Reaksmeychan',
    'មន្នី': 'Mony', 'មុន្នី': 'Mony', 'មុនី': 'Mony', 'មុន្នីនាថ': 'Monyneath', 'មុនីរ័ត្ន': 'Moniroth',
    'មុនីកា': 'Monika', 'ម៉ូនីកា': 'Monika', 'ម៉ាលី': 'Maly', 'ម៉ាលីស': 'Malis', 'ម៉ានិន': 'Manin',
    'ម៉ូនីដា': 'Monida', 'លក្ខិណា': 'Leakhena', 'លក្ខណា': 'Leakhena', 'លីកា': 'Lyka', 'លីណា': 'Lyna',
    'លីហួរ': 'Lyhour', 'លីហុង': 'Lyhong', 'លីឆាយ': 'Lychhay', 'លីដា': 'Lyda', 'លីហ្សា': 'Lysa',
    'សារឿន': 'Saroeun', 'សាវឿន': 'Savoeun', 'សារិន': 'Sarin', 'សាវិន': 'Savin', 'សារ៉ាត': 'Sarat',
    'សារ៉ាត់': 'Sarat', 'សារ៉េត': 'Sareth', 'សារ៉ាយ': 'Saray', 'សាវី': 'Savy', 'សាវ៉ាត': 'Savat',
    'ប៊ុនណា': 'Bunna', 'ប៊ិនណា': 'Binna', 'ប៊ុនថន': 'Bunthon', 'ប៊ុនធន': 'Bunthon', 'ប៊ុនរ៉ុង': 'Bunrong',
    'ប៊ុនរិទ្ធ': 'Bunrith', 'ប៊ុនណារិទ្ធ': 'Bunnarith', 'ប៊ុនហេង': 'Bunheng', 'ប៊ុនហួរ': 'Bunhour',
    'សំអុល': 'Sam Ol', 'សំអឿន': 'Samoeun', 'សំអាត': 'Samath', 'សំអាន': 'Saman', 'សំរិទ្ធ': 'Samrith',
    'ឧត្តម': 'Oudom', 'ឧត្តម្ភ': 'Oudom', 'ឧត្តមមាស': 'Oudom Meas', 'ឧត្តម្ភមាសសុទ្ធ': 'Oudom Meas Soth',
    'ច័ន្ទណារ៉ុង': 'Chan Narong', 'សាន់ច័ន្ទណារ៉ុង': 'Sanchan Narong', 'ភារៈ': 'Phearak', 'ភារុន': 'Phearun',
    'ភារម្យ': 'Phearom', 'ភារី': 'Pheary', 'ស្រស់': 'Sros', 'ស្រស់ហៀង': 'Sros Heang',
    'ស្រីពៅ': 'Sreypov', 'ស្រីម៉ៅ': 'Sreymao', 'ស្រីលីន': 'Sreylin', 'ស្រីណែត': 'Sreynet',
    'ស្រីនាង': 'Sreyniang', 'ស្រីរ័ត្ន': 'Sreyroth', 'ស្រីលក្ខ័': 'Sreyleak', 'ស្រីលក្ខណ៍': 'Sreyleak',
    'ស្រីអូន': 'Sreyoun', 'ស្រីម៉ម': 'Sreymom', 'ស្រីមុំ': 'Sreymom', 'ស្រីពេជ្រ': 'Sreypech',
    'ស្រីនិច': 'Sreynich', 'ស្រីស្រស់': 'Sreysros', 'ស្រីទូច': 'Sreytouch', 'ស្រីចិន្តា': 'Sreychinda',
    'ទីឈូ': 'Tychhou', 'ទីណា': 'Tina', 'ទីដា': 'Tyda', 'ធីតា': 'Thida', 'ធីរី': 'Thyry',
    'វត្តមានា': 'Vattana', 'សុខុមវត្តមានា': 'Sokhom Vattana', 'សោភ័ណ្ឌ': 'Sophorn', 'សុភ័ណ្ឌ': 'Sophorn',
    'រស្មីពន្លឺ': 'Reaksmey Ponloe', 'ចរិយាវត្តី': 'Chariya Vattey', 'ច័ន្ទរស្មី': 'Chan Reaksmey',
    'ច័ន្ទរិទ្ធ': 'Chanrith', 'ច័ន្ទបុប្ផា': 'Chan Bopha', 'ច័ន្ទថា': 'Chantha', 'ចរិយាសួគ៌ា': 'Chariya Suorkea',
    'ចន្ទ្រា': 'Chantrea', 'ចន្ធូ': 'Chanthou', 'ចាន់ថន': 'Chanthon', 'ចាន់នី': 'Channy',
    'ចាន់រ៉ា': 'Chanra', 'ចាន់សុផាន់ណា': 'Chansophanna', 'ចាន់ណាក់': 'Channak', 'ចាន់រិទ្ធ': 'Chanrith',
    'កញ្ញា': 'Kanya', 'កន្យា': 'Kanya', 'កាន': 'Kan', 'កុសុម': 'Kosum', 'កល្យាណ': 'Kalyan',
    'ខេមរិន្ទ': 'Khemrinth', 'ខេមរា': 'Khemara', 'ខេមរៈ': 'Khemak', 'គន្ធា': 'Kunthea',
    'គង់សាន': 'Kongsan', 'ដាវណ្ណ': 'Davann', 'ដាវី': 'Davy', 'ដុក': 'Dok', 'ឌីណា': 'Dina',
    'ឌីនីន': 'Dinin', 'ឌីម៉ង់': 'Dimang', 'ឌុច': 'Duch', 'ណារី': 'Nary', 'ណារ៉ា': 'Nara',
    'ណាសួន': 'Nasoun', 'ណុប': 'Nop', 'ណុំ': 'Nom', 'ណាត': 'Nath', 'ណាតាលី': 'Nataly',
    'ទ្រី': 'Try', 'ធី': 'Thy', 'នាង': 'Neang', 'និមល': 'Nimol', 'និស្សិត': 'Nissith',
    'នី': 'Ny', 'នីតា': 'Nita', 'នីសា': 'Nysa', 'នារី': 'Neary', 'នរិន្ទ': 'Norinth',
    'បុណ្ណវេទ': 'Bonnveth', 'បូ': 'Bo', 'បូរាមី': 'Boramy', 'បូរ៉ា': 'Bora', 'ប៉ន': 'Porn',
    'ផល្លី': 'Phally', 'ពិដោរ': 'Pidor', 'ពិសាល': 'Pisal', 'ពិសេស': 'Pises', 'ពឺន': 'Poeun',
    'ពុទ្ធាវី': 'Putheavy', 'ពូន': 'Poun', 'ភ័ស': 'Phorn', 'ភាន': 'Phean', 'ភា': 'Phea',
    'ភារិទ្ធ': 'Phearith', 'ភូមិន្ទ': 'Phouminth', 'ភូមិ': 'Phoum', 'ភួង': 'Phuong',
    'រចនា': 'Rachana', 'រតនៈ': 'Ratanak', 'រតន៍': 'Roth', 'រ័ត្ន': 'Roth', 'រុន': 'Ron',
    'រុនស្រី': 'Ronsrey', 'រ៉ន': 'Rorn', 'លន': 'Lon', 'លាង': 'Leang', 'លាងឃន': 'Leangkhon',
    'សួស': 'Suos', 'សឿន': 'Soeun', 'សេងហៃ': 'Senghai', 'សេត': 'Seth', 'សេរី': 'Serey',
    'សេរីពង្ស': 'Sereypong', 'សេស': 'Ses', 'សែត': 'Set', 'ស៊ិន': 'Sin', 'ស៊ីដារ៉ា': 'Sidara',
    'ស៊ីនាង': 'Siniang', 'ស៊ីវ': 'Siv', 'ស៊ីវហុង': 'Sivhong', 'ស៊ីវឡេង': 'Sivleng',
    'ហៀង': 'Heang', 'ហេងលី': 'Hengly', 'ឡុច': 'Loch', 'អមរា': 'Amara', 'អ៊ឹម': 'Im',
}

# Sub-syllable & phonetic tokens
KHMER_SYLLABLES_MAP: Dict[str, str] = {
    'យ៉ាន់': 'Yann', 'សាន់': 'San', 'ច័ន្ទ': 'Chan', 'ណារ៉ុង': 'Narong', 'យ៉ុន': 'Yon',
    'ភារៈ': 'Phearak', 'ឡេង': 'Leng', 'សារឿន': 'Saroeun', 'សាវឿន': 'Savoeun',
    'ប៊ុន': 'Bun', 'ប៊ិន': 'Bin', 'ណា': 'Na', 'ណី': 'Ny', 'សំ': 'Sam', 'អុល': 'Ol',
    'ឧត្តម': 'Oudom', 'ឧត្តម្ភ': 'Oudom', 'មាស': 'Meas', 'សុទ្ធ': 'Soth', 'កេត': 'Ket',
    'មុន្នី': 'Mony', 'មុនី': 'Mony', 'នាថ': 'Neath', 'កែវ': 'Keo', 'ស្រស់': 'Sros',
    'ហៀង': 'Heang', 'ខន': 'Khorn', 'សុធា': 'Sothea', 'រ៉ា': 'Ra', 'ខា': 'Kha',
    'ទី': 'Ty', 'ឈូ': 'Chhou', 'គង់': 'Kong', 'លី': 'Ly', 'កា': 'Ka', 'សុខុម': 'Sokhom',
    'វត្ត': 'Vatt', 'មានា': 'Mana', 'រិទ្ធ': 'Rith', 'រិទ្ធី': 'Rithy', 'រតនា': 'Rattana',
    'វីរៈ': 'Virak', 'វិសាល': 'Visal', 'វណ្ណៈ': 'Vannak', 'ចិន្តា': 'Chinda', 'ម៉ៅ': 'Mao',
    'សុខ': 'Sok', 'ជា': 'Chea', 'រឿន': 'Roeun', 'សួស': 'Suos', 'ចរិយា': 'Chariya',
    'ថា': 'Tha', 'លីន': 'Lin', 'ណែត': 'Net', 'នាង': 'Niang', 'ពៅ': 'Pov', 'ម៉ម': 'Mom',
    'ផន': 'Phorn', 'ផល': 'Phal', 'ផាត់': 'Phat', 'ផេង': 'Pheng', 'ហួត': 'Huot', 'ហុង': 'Hong',
}

# Phonetic character transliteration tables (Fallback parser)
CONSONANTS = {
    'ក': 'K', 'ខ': 'Kh', 'គ': 'K', 'ឃ': 'Kh', 'ង': 'Ng',
    'ច': 'Ch', 'ឆ': 'Chh', 'ជ': 'Ch', 'ឈ': 'Chh', 'ញ': 'Nh',
    'ដ': 'D', 'ឋ': 'Th', 'ឌ': 'D', 'ឍ': 'Th', 'ណ': 'N',
    'ត': 'T', 'ថ': 'Th', 'ទ': 'T', 'ធ': 'Th', 'ន': 'N',
    'ប': 'B', 'ផ': 'Ph', 'ព': 'P', 'ភ': 'Ph', 'ម': 'M',
    'យ': 'Y', 'រ': 'R', 'ល': 'L', 'វ': 'V', 'ស': 'S',
    'ហ': 'H', 'ឡ': 'L', 'អ': 'A',
}

INDEPENDENT_VOWELS = {
    'ឥ': 'E', 'ឦ': 'Ey', 'ឧ': 'Ou', 'ឩ': 'Ou', 'ឪ': 'Auv',
    'ឫ': 'Reu', 'ឬ': 'Reu', 'ឭ': 'Leu', 'ឮ': 'Leu',
    'ឯ': 'Ae', 'ឰ': 'Ai', 'ឱ': 'Ao', 'ឲ': 'Ao', 'ឳ': 'Auv'
}

VOWEL_SIGNS = {
    'ា': 'a', 'ិ': 'e', 'ី': 'ey', 'ឹ': 'oe', 'ឺ': 'eu',
    'ុ': 'o', 'ូ': 'ou', 'ួ': 'uo', 'ើ': 'oe', 'ឿ': 'oeu',
    'ៀ': 'ie', 'េ': 'e', 'ែ': 'ae', 'ៃ': 'ai', 'ោ': 'ao',
    'ៅ': 'au', 'ុំ': 'om', 'ំ': 'om', 'ាំ': 'am', 'ះ': 'ah', 'ៈ': 'ak',
    '័': 'a', '៏': 'or', '៉': '', '៊': '', '់': '', '៍': '', '៌': '', '៎': '',
    '្': '' # Coeng
}


def _romanize_phonetic_word(word: str) -> str:
    """
    Fallback rule-based syllable decomposition for words not in the curated dictionary.
    Guarantees 100% clean Latin output with zero Khmer characters.
    """
    if not word:
        return ''

    # 1. Direct dictionary lookup
    if word in KHMER_NAME_DICTIONARY:
        return KHMER_NAME_DICTIONARY[word]
    if word in KHMER_SYLLABLES_MAP:
        return KHMER_SYLLABLES_MAP[word]

    # 2. Try compound sub-words segment matching
    # E.g. 'សាន់ច័ន្ទណារ៉ុង' -> 'សាន់' (San) + 'ច័ន្ទ' (Chan) + 'ណារ៉ុង' (Narong)
    for l in range(min(12, len(word)), 1, -1):
        prefix = word[:l]
        if prefix in KHMER_SYLLABLES_MAP or prefix in KHMER_NAME_DICTIONARY:
            p_val = KHMER_SYLLABLES_MAP.get(prefix) or KHMER_NAME_DICTIONARY.get(prefix)
            rest_val = _romanize_phonetic_word(word[l:])
            return f"{p_val}{' ' + rest_val if rest_val else ''}".strip()

    # 3. Phonetic character-by-character mapping
    out = []
    i = 0
    w_len = len(word)
    while i < w_len:
        ch = word[i]
        
        # Check independent vowels
        if ch in INDEPENDENT_VOWELS:
            out.append(INDEPENDENT_VOWELS[ch])
            i += 1
            continue

        # Check coeng (subscript consonant: ្ + consonant)
        if ch == '្' and i + 1 < w_len:
            next_ch = word[i + 1]
            c_val = CONSONANTS.get(next_ch, '').lower()
            if c_val:
                out.append(c_val)
            i += 2
            continue

        # Check consonant
        if ch in CONSONANTS:
            # Lookahead: is there a silent mark (ទណ្ឌឃាត '៍') on this consonant?
            if i + 1 < w_len and word[i + 1] == '៍':
                i += 2
                continue
            
            c_val = CONSONANTS[ch]
            # If not initial letter in this sub-token, use lowercase
            if out:
                c_val = c_val.lower()
            out.append(c_val)
            i += 1
            continue

        # Check vowel signs and diacritics
        if ch in VOWEL_SIGNS:
            v_val = VOWEL_SIGNS[ch]
            if v_val:
                out.append(v_val)
            i += 1
            continue

        # Skip any unknown or non-Khmer non-Latin unicode
        i += 1

    res = ''.join(out).strip()
    # Strip any stray Khmer characters just in case
    res = re.sub(r'[\u1780-\u17FF]', '', res)
    return res.capitalize() if res else ''


def romanize_khmer_name(khmer_name: str) -> str:
    """
    Translates a full Khmer name into clean, standardized Latin script.
    
    Examples:
    - យ៉ាន់ សាន់ច័ន្ទណារ៉ុង -> Yann Sanchan Narong
    - យ៉ុន ភារៈ -> Yon Phearak
    - ឡេងសាវឿន ប៊ិនណា -> Leng Savoeun Binna
    - សំអុល ឧត្តម្ភមាសសុទ្ធ -> Sam Ol Oudom Meas Soth
    - កេត មុន្នីនាថ -> Ket Monyneath
    - កែវ ស្រស់ហៀង -> Keo Sros Heang
    - គង់ សុខុមវត្តមានា -> Kong Sokhom Vattana
    """
    if not khmer_name:
        return ''

    # Normalize zero-width spaces and whitespace
    cleaned = khmer_name.replace('\u200b', ' ').replace('\xa0', ' ').strip()
    words = cleaned.split()

    latin_words: List[str] = []
    for word in words:
        w_clean = word.strip()
        if not w_clean:
            continue

        # Check direct dictionary lookup first
        if w_clean in KHMER_NAME_DICTIONARY:
            latin_words.append(KHMER_NAME_DICTIONARY[w_clean])
        else:
            # Phonetic segmentation and conversion
            rom_val = _romanize_phonetic_word(w_clean)
            if rom_val:
                latin_words.append(rom_val)

    result = ' '.join(latin_words)
    # Ensure 100% clean Latin with proper spacing and Title Case
    result = re.sub(r'\s+', ' ', result).strip()
    # Capitalize each word properly
    words_cap = [w.capitalize() if not w.isupper() else w for w in result.split()]
    return ' '.join(words_cap)
