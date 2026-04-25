import math
import re
import ipaddress
import unicodedata
import urllib.parse
try:
    import tldextract
    HAS_TLDEXTRACT = True
except Exception:
    HAS_TLDEXTRACT = False

# lookup sets for fast matching
TOP_100_TLDS = {
    'com': 1, 'net': 2, 'org': 3, 'io': 4, 'arpa': 5, 'dev': 6, 'tv': 7, 'google': 8, 'co': 9, 'cn': 10,
    'ms': 11, 'ai': 12, 'us': 13, 'goog': 14, 'me': 15, 'microsoft': 16, 'one': 17, 'app': 18, 'eu': 19, 'de': 20,
    'cloud': 21, 'tech': 22, 'ru': 23, 'xyz': 24, 'apple': 25, 'jp': 26, 'uk': 27, 'cc': 28, 'mobi': 29, 'it': 30,
    'gov': 31, 'local': 32, 'info': 33, 'gg': 34, 'localdomain': 35, 'site': 36, 'br': 37, 'in': 38, 'top': 39, 'fr': 40,
    'network': 41, 'solutions': 42, 'online': 43, 'ca': 44, 'services': 45, 'be': 46, 'to': 47, 'live': 48, 'pl': 49, 'link': 50,
    'media': 51, 'nl': 52, 'im': 53, 'biz': 54, 'sh': 55, 'kr': 56, 'au': 57, 'lan': 58, 'fi': 59, 'pro': 60,
    'tr': 61, 'es': 62, 'gt': 63, 'so': 64, 'se': 65, 'news': 66, 'ch': 67, 'home': 68, 'shop': 69, 'invalid': 70,
    'id': 71, 'no': 72, 'sg': 73, 'edu': 74, 'cz': 75, 'mx': 76, 'at': 77, 'aws': 78, 'store': 79, 'fun': 80,
    'amazon': 81, 'club': 82, 'fm': 83, 'ac': 84, 'nz': 85, 'talk': 86, 'kz': 87, 'vn': 88, 'sk': 89, 'tw': 90,
    'st': 91, 'video': 92, 'dk': 93, 'gr': 94, 'vip': 95, 'space': 96, 'ar': 97, 'my': 98, 'ws': 99, 'systems': 100
}

TARGET_BRANDS = {
    'paypal', 'apple', 'google', 'microsoft', 'yahoo', 'appleid',
    'adobe', 'alibaba', 'usps', 'dhl', 'aol', 'amazon'
}

SOCIAL_ENG_WORDS = {
    'login', 'account', 'update', 'secure', 'signin', 'admin', 'support', 'customer', 'email',
    'webmail', 'verify', 'verification', 'user', 'userid', 'myaccount', 'security'
}

ABUSED_HOSTING_CMS = {
    'weebly', '000webhostapp', 'plugins', 'themes', 'uploads', 'content', 'includes', 'docs', 'blog',
    'ipfs', 'gitbook', 'weeblysite', 'pages', 'cloudflare', 'dropbox', 'firebaseapp',
    'wixsite', 'blogspot', 'webcindario', 'mybluehost'
}

SUS_FILE_EXTS = {
    'exe', 'php', 'htm', 'html', 'pdf', 'cgi', 'asp', 'aspx', 'shtml', 'bin', 'css',
    'sh', 'js', 'doc', 'zip', 'dll', 'txt', 'aspxn'
}

TECH_EXEC_WORDS = {
    'cmd', 'x86', 'mips', 'delayms', 'loop', 'false', 'raw', 'bins',
    'dev', 'downloads', '2pacx', 'rand', 'sshd', 'proxy', 'crypted', 'malw'
}

SHORTENER_DOMAINS = {
    "2s.ms", "adf.ly", "bit.do", "bit.ly", "buff.ly", "chatg.pt", "cutt.ly", "dub.co", "dub.sh",
    "ggl.link", "git.new", "is.gd", "j.mp", "ln.run", "ow.ly", "rb.gy", "rebrand.ly", "short.gy",
    "shorturl.at", "spti.fi", "sw.run", "t.co", "t.ly", "t2m.io", "tiny.cc", "tiny.one",
    "tinyurl.com", "v.gd"
}

REDIRECT_KEYS = {
    "url", "target", "dest", "destination", "redir", "redirect",
    "redirect_uri", "next", "continue", "return", "returnto", "r"
}

DOC_LIKE_EXTS = {"pdf", "doc", "docx", "xls", "xlsx", "txt", "rtf", "html", "htm"}
EXEC_LIKE_EXTS = {"exe", "dll", "js", "jar", "php", "asp", "aspx", "cgi", "sh", "bin"}

VOWELS = set("aeiou")
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")
DIGITS = set("0123456789")

# --- helpers ---

def calculate_entropy(text: str) -> float:
    if not text:
        return 0.0
    entropy = 0.0
    n = len(text)
    for ch in set(text):
        p = text.count(ch) / n
        entropy -= p * math.log(p, 2)
    return entropy


def get_char_counts(text: str, prefix: str = "") -> dict:
    if not text:
        return {
            f"{prefix}letter_cnt": 0,
            f"{prefix}digit_cnt": 0,
            f"{prefix}special_cnt": 0,
        }

    letter_cnt = sum(c.isalpha() for c in text)
    digit_cnt = sum(c.isdigit() for c in text)
    special_cnt = sum(not c.isalnum() for c in text)

    return {
        f"{prefix}letter_cnt": letter_cnt,
        f"{prefix}digit_cnt": digit_cnt,
        f"{prefix}special_cnt": special_cnt,
    }


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            ins = previous_row[j + 1] + 1
            dele = current_row[j] + 1
            sub = previous_row[j] + (c1 != c2)
            current_row.append(min(ins, dele, sub))
        previous_row = current_row

    return previous_row[-1]


def get_max_consecutive(text: str, char_set: set) -> int:
    max_count = 0
    cur = 0
    for ch in text.lower():
        if ch in char_set:
            cur += 1
            max_count = max(max_count, cur)
        else:
            cur = 0
    return max_count


def get_max_repeated_char_run(text: str) -> int:
    if not text:
        return 0
    max_run = 1
    cur = 1
    prev = text[0]
    for ch in text[1:]:
        if ch == prev:
            cur += 1
            max_run = max(max_run, cur)
        else:
            cur = 1
            prev = ch
    return max_run


def tokenise_text(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok]


def safe_unquote(text: str) -> str:
    try:
        return urllib.parse.unquote(text)
    except Exception:
        return text


def normalise_brand_candidate(text: str) -> str:
    if not text:
        return ""
    text = text.lower().replace("-", "").replace("_", "")
    text = re.sub(r"[^a-z0-9]", "", text)
    # basic leetspeak conversion
    trans = str.maketrans({
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b"
    })
    return text.translate(trans)


def get_unicode_script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    if ord(ch) < 128:
        return "latin"
    name = unicodedata.name(ch, "")
    if "LATIN" in name:
        return "latin"
    if "CYRILLIC" in name:
        return "cyrillic"
    if "GREEK" in name:
        return "greek"
    return "other"


def decompose_hostname(hostname: str) -> tuple[str, str, str, list[str], list[str]]:
    # breaks down the host (returns: domain, label, tld suffix, subdomains, all labels)
    hostname = (hostname or "").strip(".").lower()
    if not hostname:
        return "", "", "", [], []

    all_labels = [x for x in hostname.split(".") if x]

    if HAS_TLDEXTRACT:
        ext = tldextract.extract(hostname)
        reg_domain = ".".join([p for p in [ext.domain, ext.suffix] if p])
        reg_label = ext.domain or ""
        suffix = ext.suffix or ""
        sub_labels = [x for x in ext.subdomain.split(".") if x] if ext.subdomain else []
        return reg_domain, reg_label, suffix, sub_labels, all_labels

    # fallback if no tldextract
    if len(all_labels) >= 2:
        suffix = all_labels[-1]
        reg_label = all_labels[-2]
        reg_domain = f"{reg_label}.{suffix}"
        sub_labels = all_labels[:-2]
    else:
        suffix = ""
        reg_label = all_labels[0]
        reg_domain = reg_label
        sub_labels = []

    return reg_domain, reg_label, suffix, sub_labels, all_labels


def get_ip_features(hostname: str) -> dict:
    ip_feats = {
        "is_ip": 0,
        "is_ipv4": 0,
        "is_ipv6": 0,
        "is_private_ip": 0,
        "is_loopback_ip": 0,
        "is_reserved_ip": 0,
    }

    if not hostname:
        return ip_feats

    host = hostname.strip("[]")
    try:
        ip_obj = ipaddress.ip_address(host)
        ip_feats["is_ip"] = 1
        ip_feats["is_ipv4"] = int(ip_obj.version == 4)
        ip_feats["is_ipv6"] = int(ip_obj.version == 6)
        ip_feats["is_private_ip"] = int(ip_obj.is_private)
        ip_feats["is_loopback_ip"] = int(ip_obj.is_loopback)
        ip_feats["is_reserved_ip"] = int(ip_obj.is_reserved)
    except Exception:
        pass

    return ip_feats


# --- core extraction logic ---
def extract_features(url: str) -> dict | None:
    if url is None:
        return None

    raw_url = str(url).strip()
    if not raw_url:
        return None

    url_len = len(raw_url)
    raw_url_lower = raw_url.lower()

    # force a scheme so urllib does not error but keep original for raw features
    parse_url = raw_url if re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", raw_url) else "http://" + raw_url

    try:
        parsed = urllib.parse.urlsplit(parse_url)
        hostname = (parsed.hostname or "").lower()
        path = parsed.path or ""
        query = parsed.query or ""
        fragment = parsed.fragment or ""
        scheme = (parsed.scheme or "").lower()
        netloc = parsed.netloc or ""

        try:
            port = parsed.port
        except Exception:
            port = None
    except Exception:
        return None

    decoded_path = safe_unquote(path)
    decoded_query = safe_unquote(query)

    url_counts = get_char_counts(raw_url, "")
    host_counts = get_char_counts(hostname, "host_")
    path_counts = get_char_counts(path, "path_")
    query_counts = get_char_counts(query, "query_")
    frag_counts = get_char_counts(fragment, "frag_")

    ip_feats = get_ip_features(hostname)

    reg_domain, reg_label, suffix, sub_labels, all_labels = decompose_hostname(hostname)
    tld = suffix.split(".")[-1] if suffix else ""

    tokens_url = tokenise_text(raw_url_lower)
    tokens_host = tokenise_text(hostname)
    tokens_path = tokenise_text(decoded_path.lower())
    tokens_query = tokenise_text(decoded_query.lower())
    tokens_all = tokens_url

    host_vowels = sum(1 for c in hostname if c in VOWELS)
    host_consonants = sum(1 for c in hostname if c in CONSONANTS)
    vowel_consonant_ratio = (host_vowels / host_consonants) if host_consonants > 0 else 0.0

    path_segments = [p for p in path.split("/") if p]
    directory_depth = len(path_segments)

    last_seg = path.rstrip("/").rsplit("/", 1)[-1].lower() if path else ""
    exts = re.findall(r"\.([a-z0-9]{1,10})(?=\.|$)", last_seg)

    query_pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    query_keys = [k.lower() for k, _ in query_pairs]

    redirect_param_present = int(any(k in REDIRECT_KEYS for k in query_keys))
    embedded_url_in_query = int(
        ("http://" in decoded_query.lower()) or
        ("https://" in decoded_query.lower()) or
        any(("http://" in safe_unquote(v).lower()) or ("https://" in safe_unquote(v).lower()) for _, v in query_pairs)
    )
    embedded_url_in_path = int(("http://" in decoded_path.lower()) or ("https://" in decoded_path.lower()))

    brand_token_cnt = sum(tok in TARGET_BRANDS for tok in tokens_all)
    social_eng_token_cnt = sum(tok in SOCIAL_ENG_WORDS for tok in tokens_all)
    tech_exec_token_cnt = sum(tok in TECH_EXEC_WORDS for tok in tokens_all)
    abused_hosting_token_cnt = sum(tok in ABUSED_HOSTING_CMS for tok in (tokens_host + tokens_path + tokens_query))
    abused_hosting_substring_cnt = sum(term in raw_url_lower for term in ABUSED_HOSTING_CMS if len(term) >= 6)

    # check if they are spoofing a brand
    norm_reg_label = normalise_brand_candidate(reg_label)
    min_brand_dist = 999
    brand_in_reg_domain = 0
    reg_startswith_brand = 0
    reg_endswith_brand = 0

    for brand in TARGET_BRANDS:
        norm_brand = normalise_brand_candidate(brand)
        if not norm_reg_label or not norm_brand:
            continue
        dist = levenshtein_distance(norm_reg_label, norm_brand)
        if dist < min_brand_dist:
            min_brand_dist = dist
        if norm_brand in norm_reg_label:
            brand_in_reg_domain = 1
            if norm_reg_label.startswith(norm_brand):
                reg_startswith_brand = 1
            if norm_reg_label.endswith(norm_brand):
                reg_endswith_brand = 1

    if min_brand_dist == 999:
        min_brand_dist = 0

    is_typosquat = int(
        norm_reg_label != "" and
        any(
            1 <= levenshtein_distance(norm_reg_label, normalise_brand_candidate(brand)) <= 2
            for brand in TARGET_BRANDS
        )
    )

    # catch homograph attacks and weird charsets
    host_scripts = {s for ch in hostname for s in [get_unicode_script(ch)] if s is not None}
    has_non_ascii_host = int(any(ord(ch) > 127 for ch in hostname))
    host_mixed_script = int(len(host_scripts) > 1)
    punycode_label_cnt = sum(label.startswith("xn--") for label in all_labels)

    # spot weirdly generated subdomains (lots of numbers/hyphens)
    label_lens = [len(lbl) for lbl in all_labels] if all_labels else [0]
    label_entropies = [calculate_entropy(lbl) for lbl in all_labels] if all_labels else [0.0]
    digit_heavy_label_cnt = sum((sum(c.isdigit() for c in lbl) / len(lbl)) > 0.3 for lbl in all_labels if lbl)
    hyphenated_label_cnt = sum("-" in lbl for lbl in all_labels if lbl)

    # flag weird ports, embedded creds, or double schemes
    original_has_scheme = int(bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", raw_url)))
    has_userinfo = int("@" in netloc and hostname != "")
    has_fragment = int(bool(fragment))
    has_port = int(port is not None)
    port_is_nondefault = int(
        port is not None and (
            (scheme == "http" and port != 80) or
            (scheme == "https" and port != 443) or
            (scheme not in {"http", "https"})
        )
    )
    double_scheme_cnt = len(re.findall(r"https?://", raw_url_lower))
    double_slash_in_path = int("//" in path)
    hostname_startswith_www_digit = int(bool(re.match(r"^www\d+\.", hostname)))

    # look for url-encoded tricks
    num_encoded_chars = len(re.findall(r"%[0-9a-fA-F]{2}", raw_url))
    decoded_has_brand = sum(tok in TARGET_BRANDS for tok in tokenise_text((decoded_path + " " + decoded_query).lower()))
    decoded_has_http = int(("http://" in decoded_path.lower()) or ("https://" in decoded_path.lower()) or
                           ("http://" in decoded_query.lower()) or ("https://" in decoded_query.lower()))

    # flag shortlinks
    is_shortened = int(hostname in SHORTENER_DOMAINS or reg_domain in SHORTENER_DOMAINS)

    # catch sketchy drops (e.g. file.pdf.exe)
    path_has_extension = int(len(exts) > 0)
    is_suspicious_ext = int(exts[-1] in SUS_FILE_EXTS) if exts else 0
    has_double_extension = int(len(exts) >= 2)
    doc_exec_mismatch_ext = int(
        len(exts) >= 2 and
        any(ext in DOC_LIKE_EXTS for ext in exts[:-1]) and
        (exts[-1] in EXEC_LIKE_EXTS)
    )

    # overall makeup of the string
    digit_ratio = url_counts["digit_cnt"] / url_len
    letter_ratio = url_counts["letter_cnt"] / url_len
    spec_ratio = url_counts["special_cnt"] / url_len
    path_depth_ratio = directory_depth / url_len

    features = {
        # lengths
        "url_len": url_len,
        "host_len": len(hostname),
        "path_len": len(path),
        "query_len": len(query),
        "fragment_len": len(fragment),
        "reg_domain_len": len(reg_domain),
        "reg_label_len": len(reg_label),
        "suffix_len": len(suffix),
        "tld_len": len(tld),

        # raw counts
        "letter_cnt": url_counts["letter_cnt"],
        "digit_cnt": url_counts["digit_cnt"],
        "special_cnt": url_counts["special_cnt"],
        "dot_cnt": raw_url.count("."),
        "dash_cnt": raw_url.count("-"),
        "under_cnt": raw_url.count("_"),
        "slash_cnt": raw_url.count("/"),
        "at_cnt": raw_url.count("@"),
        "percent_cnt": raw_url.count("%"),
        "equal_cnt": raw_url.count("="),
        "question_cnt": raw_url.count("?"),
        "amp_cnt": raw_url.count("&"),
        "colon_cnt": raw_url.count(":"),
        "hash_cnt": raw_url.count("#"),

        # chunk-specific counts
        "host_letter_cnt": host_counts["host_letter_cnt"],
        "host_digit_cnt": host_counts["host_digit_cnt"],
        "host_special_cnt": host_counts["host_special_cnt"],
        "path_letter_cnt": path_counts["path_letter_cnt"],
        "path_digit_cnt": path_counts["path_digit_cnt"],
        "path_special_cnt": path_counts["path_special_cnt"],
        "query_letter_cnt": query_counts["query_letter_cnt"],
        "query_digit_cnt": query_counts["query_digit_cnt"],
        "query_special_cnt": query_counts["query_special_cnt"],
        "frag_letter_cnt": frag_counts["frag_letter_cnt"],
        "frag_digit_cnt": frag_counts["frag_digit_cnt"],
        "frag_special_cnt": frag_counts["frag_special_cnt"],

        # proportions
        "letter_ratio": letter_ratio,
        "digit_ratio": digit_ratio,
        "spec_ratio": spec_ratio,
        "path_depth_ratio": path_depth_ratio,
        "vowel_consonant_ratio": vowel_consonant_ratio,

        # domain stats
        "subdom_cnt": len(sub_labels),
        "label_cnt": len(all_labels),
        "common_tld": TOP_100_TLDS.get(tld, 0),   # kept for compatibility
        "is_known_tld": int(tld in TOP_100_TLDS),
        "is_cc_tld": int(len(tld) == 2),
        "has_punycode": int("xn--" in hostname),
        "punycode_label_cnt": punycode_label_cnt,
        "has_non_ascii_host": has_non_ascii_host,
        "host_mixed_script": host_mixed_script,
        "max_label_len": max(label_lens) if label_lens else 0,
        "min_label_len": min(label_lens) if label_lens else 0,
        "avg_label_len": sum(label_lens) / len(label_lens) if label_lens else 0.0,
        "avg_label_entropy": sum(label_entropies) / len(label_entropies) if label_entropies else 0.0,
        "digit_heavy_label_cnt": digit_heavy_label_cnt,
        "hyphenated_label_cnt": hyphenated_label_cnt,

        # ip flags
        **ip_feats,

        # randomness scores
        "entropy": calculate_entropy(raw_url),
        "host_entropy": calculate_entropy(hostname),
        "path_entropy": calculate_entropy(path),
        "query_entropy": calculate_entropy(query),

        # protocol quirks
        "original_has_scheme": original_has_scheme,
        "scheme_http": int(scheme == "http"),
        "scheme_https": int(scheme == "https"),
        "scheme_other": int(scheme not in {"http", "https"}),
        "has_userinfo": has_userinfo,
        "has_port": has_port,
        "port_is_nondefault": port_is_nondefault,
        "has_fragment": has_fragment,
        "double_scheme_cnt": double_scheme_cnt,
        "double_slash_in_path": double_slash_in_path,
        "hostname_startswith_www_digit": hostname_startswith_www_digit,

        # protocol hiding
        "http_in_host": int("http" in hostname),
        "https_in_host": int("https" in hostname),
        "http_in_path": int("http" in path.lower()),
        "https_in_path": int("https" in path.lower()),
        "http_in_query": int("http" in query.lower()),
        "https_in_query": int("https" in query.lower()),

        # sketchy keyword hits
        "has_brand_spoof": brand_token_cnt,
        "has_social_eng": social_eng_token_cnt,
        "has_abused_hosting": abused_hosting_token_cnt + abused_hosting_substring_cnt,
        "has_tech_exec": tech_exec_token_cnt,

        # brand spoofing metrics
        "is_typosquat": is_typosquat,
        "min_brand_dist": min_brand_dist,
        "brand_in_reg_domain": brand_in_reg_domain,
        "reg_startswith_brand": reg_startswith_brand,
        "reg_endswith_brand": reg_endswith_brand,

        # evasion tactics
        "num_encoded_chars": num_encoded_chars,
        "decoded_path_delta": len(decoded_path) - len(path),
        "decoded_query_delta": len(decoded_query) - len(query),
        "decoded_has_brand": decoded_has_brand,
        "decoded_has_http": decoded_has_http,
        "query_param_cnt": len(query_pairs),
        "query_key_unique_cnt": len(set(query_keys)),
        "redirect_param_present": redirect_param_present,
        "embedded_url_in_query": embedded_url_in_query,
        "embedded_url_in_path": embedded_url_in_path,

        # file & directory intel
        "directory_depth": directory_depth,
        "path_segment_cnt": len(path_segments),
        "path_has_extension": path_has_extension,
        "num_extensions_last_seg": len(exts),
        "has_sus_file_ext": is_suspicious_ext,
        "has_double_extension": has_double_extension,
        "doc_exec_mismatch_ext": doc_exec_mismatch_ext,

        # keyboard mashing indicators
        "max_consec_digits": max(get_max_consecutive(hostname, DIGITS), get_max_consecutive(path, DIGITS)),
        "max_consec_consonants": max(get_max_consecutive(hostname, CONSONANTS), get_max_consecutive(path, CONSONANTS)),
        "max_repeated_char_run": get_max_repeated_char_run(hostname + path),

        # token sizes
        "host_token_cnt": len(tokens_host),
        "path_token_cnt": len(tokens_path),
        "query_token_cnt": len(tokens_query),
        "url_token_cnt": len(tokens_all),

        # infra
        "is_shortened": is_shortened,
    }

    return features