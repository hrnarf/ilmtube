"""The 114 surahs: (English transliteration, Arabic). Source of surahs.json and surah-query variants."""
import re

SURAHS = [
("Al-Fatihah","الفاتحة"),("Al-Baqarah","البقرة"),("Aal-E-Imran","آل عمران"),("An-Nisa","النساء"),("Al-Ma'idah","المائدة"),
("Al-An'am","الأنعام"),("Al-A'raf","الأعراف"),("Al-Anfal","الأنفال"),("At-Tawbah","التوبة"),("Yunus","يونس"),
("Hud","هود"),("Yusuf","يوسف"),("Ar-Ra'd","الرعد"),("Ibrahim","إبراهيم"),("Al-Hijr","الحجر"),
("An-Nahl","النحل"),("Al-Isra","الإسراء"),("Al-Kahf","الكهف"),("Maryam","مريم"),("Ta-Ha","طه"),
("Al-Anbiya","الأنبياء"),("Al-Hajj","الحج"),("Al-Mu'minun","المؤمنون"),("An-Nur","النور"),("Al-Furqan","الفرقان"),
("Ash-Shu'ara","الشعراء"),("An-Naml","النمل"),("Al-Qasas","القصص"),("Al-Ankabut","العنكبوت"),("Ar-Rum","الروم"),
("Luqman","لقمان"),("As-Sajdah","السجدة"),("Al-Ahzab","الأحزاب"),("Saba","سبأ"),("Fatir","فاطر"),
("Ya-Sin","يس"),("As-Saffat","الصافات"),("Sad","ص"),("Az-Zumar","الزمر"),("Ghafir","غافر"),
("Fussilat","فصلت"),("Ash-Shura","الشورى"),("Az-Zukhruf","الزخرف"),("Ad-Dukhan","الدخان"),("Al-Jathiyah","الجاثية"),
("Al-Ahqaf","الأحقاف"),("Muhammad","محمد"),("Al-Fath","الفتح"),("Al-Hujurat","الحجرات"),("Qaf","ق"),
("Adh-Dhariyat","الذاريات"),("At-Tur","الطور"),("An-Najm","النجم"),("Al-Qamar","القمر"),("Ar-Rahman","الرحمن"),
("Al-Waqi'ah","الواقعة"),("Al-Hadid","الحديد"),("Al-Mujadila","المجادلة"),("Al-Hashr","الحشر"),("Al-Mumtahanah","الممتحنة"),
("As-Saff","الصف"),("Al-Jumu'ah","الجمعة"),("Al-Munafiqun","المنافقون"),("At-Taghabun","التغابن"),("At-Talaq","الطلاق"),
("At-Tahrim","التحريم"),("Al-Mulk","الملك"),("Al-Qalam","القلم"),("Al-Haqqah","الحاقة"),("Al-Ma'arij","المعارج"),
("Nuh","نوح"),("Al-Jinn","الجن"),("Al-Muzzammil","المزمل"),("Al-Muddaththir","المدثر"),("Al-Qiyamah","القيامة"),
("Al-Insan","الإنسان"),("Al-Mursalat","المرسلات"),("An-Naba","النبأ"),("An-Nazi'at","النازعات"),("Abasa","عبس"),
("At-Takwir","التكوير"),("Al-Infitar","الانفطار"),("Al-Mutaffifin","المطففين"),("Al-Inshiqaq","الانشقاق"),("Al-Buruj","البروج"),
("At-Tariq","الطارق"),("Al-A'la","الأعلى"),("Al-Ghashiyah","الغاشية"),("Al-Fajr","الفجر"),("Al-Balad","البلد"),
("Ash-Shams","الشمس"),("Al-Layl","الليل"),("Ad-Duha","الضحى"),("Ash-Sharh","الشرح"),("At-Tin","التين"),
("Al-Alaq","العلق"),("Al-Qadr","القدر"),("Al-Bayyinah","البينة"),("Az-Zalzalah","الزلزلة"),("Al-Adiyat","العاديات"),
("Al-Qari'ah","القارعة"),("At-Takathur","التكاثر"),("Al-Asr","العصر"),("Al-Humazah","الهمزة"),("Al-Fil","الفيل"),
("Quraysh","قريش"),("Al-Ma'un","الماعون"),("Al-Kawthar","الكوثر"),("Al-Kafirun","الكافرون"),("An-Nasr","النصر"),
("Al-Masad","المسد"),("Al-Ikhlas","الإخلاص"),("Al-Falaq","الفلق"),("An-Nas","الناس"),
]
assert len(SURAHS) == 114

# Extra common spellings, keyed by surah number.
EXTRA = {1: ["fatiha", "fateha"], 2: ["baqara", "baqarah", "baqra"], 3: ["imran", "ali imran", "al imran", "aal imran", "al-i-imran"],
         4: ["nisaa"], 9: ["tawba", "tauba", "taubah", "bara'ah"], 12: ["yousuf", "yosuf"], 18: ["kahf", "kahaf", "kehf"], 19: ["mariam"],
         20: ["taha", "ta ha"], 36: ["yasin", "yaseen", "ya sin", "ya-seen"], 55: ["rahman", "rehman"], 56: ["waqia", "waqiah", "waqi'a"],
         67: ["mulk", "tabarak", "tabaarak"], 62: ["jumuah", "jumua"], 72: ["jinn"], 73: ["muzammil", "muzzamil"], 74: ["mudaththir", "muddathir"],
         78: ["naba", "amma"], 93: ["duha", "dhuha"], 94: ["sharh", "inshirah", "alam nashrah"], 97: ["qadr"], 103: ["asr"], 105: ["fil"],
         107: ["maun"], 108: ["kausar", "kawsar"], 109: ["kafirun", "kafiroon"], 110: ["nasr"], 112: ["ikhlas", "ikhlaas"], 113: ["falaq"], 114: ["nas", "naas"]}


def norm(s: str) -> str:
    s = s.lower().replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def variants(n: int) -> list[str]:
    name, ar = SURAHS[n - 1]
    base = norm(name)
    out = {base, base.replace(" ", ""), ar}
    stripped = re.sub(r"^(al|an|ar|as|at|az|ad|ash|adh|aal) ", "", base)
    if stripped != base:
        out |= {stripped, stripped.replace(" ", "")}
    out |= {norm(v) for v in EXTRA.get(n, [])}
    out |= {f"surah {n}", f"surat {n}", f"chapter {n}"}
    return sorted(v for v in out if v)
