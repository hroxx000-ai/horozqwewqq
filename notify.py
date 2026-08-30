"""
GITHUB TOPLU BILDIRIM ACMA SCRIPTI (genis kapsam / yuksek hacim surumu)
=========================================================================
Bu script GitHub'daki cok sayida populer/hareketli public repoyu bulup
hepsini "Watch" (izle) durumuna getirir. Boylece bu repolarda yeni
commit, issue, pull request veya tartisma oldukca Gmail'ine bildirim
e-postasi gelmeye baslar.

ONEMLI GERCEKLER:
- Watch etmek ANINDA e-posta URETMEZ. E-postalar, izledigin repolarda
  ILERIDE olacak hareketlerle birlikte zamanla birikir.
- GitHub arama API'si TEK SORGUDA EN FAZLA 1000 sonuc verir (sabit bir
  kural). Bu yuzden cok sayida repo toplamak icin arama, farkli yildiz
  araliklarina (STAR_BUCKETS) bolunerek tekrarlanir.
- TOP_N = 50000 olarak ayarlanmis olsa da, gercekte GitHub'da o kadar
  "anlamli / aktif" repo olmayabilir; script bulabildigi kadarini alir.

KULLANIM:
1. TOKEN, GH_TOKEN adinda bir GitHub Actions secret'indan otomatik gelir.
2. TOP_N sayisini asagidan ayarla.
3. Scripti calistir (GitHub Actions -> Run workflow).
"""

import os
import time
import datetime
import requests

TOKEN = os.environ.get("GH_TOKEN", "YOUR_GITHUB_TOKEN")
TOP_N = 50000  # <-- hedef ust sinir (gercekte bulunabilen kadari islenir)

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

SEARCH_URL = "https://api.github.com/search/repositories"

# Yildiz sayisina gore arama havuzunu genisletmek icin bolunmus araliklar.
# Her aralik GitHub arama API'sinde ayri bir sorgu sayilir, boylece
# 1000 sonuc sinirini asip cok daha genis bir repo havuzu toplariz.
STAR_BUCKETS = [
    "stars:>50000",
    "stars:20000..50000",
    "stars:10000..20000",
    "stars:5000..10000",
    "stars:2000..5000",
    "stars:1000..2000",
    "stars:500..1000",
    "stars:200..500",
    "stars:100..200",
    "stars:50..100",
]


def request_with_retry(method, url, retries=5, **kwargs):
    """Rate limit'e (hiz sinirina) takilirsa GitHub'in soyledigi sureyi
    bekleyip tekrar dener. Boylece script hata verip yarida durmaz."""
    for attempt in range(retries):
        r = requests.request(method, url, headers=HEADERS, **kwargs)
        if r.status_code in (200, 201, 204):
            return r
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = r.headers.get("X-RateLimit-Reset")
            wait = 30
            if reset:
                wait = max(5, int(reset) - int(time.time()) + 2)
            print(f"   ⏳ Hız sınırı doldu, {wait} saniye bekleniyor...")
            time.sleep(min(wait, 120))
            continue
        return r  # baska bir hata ise oldugu gibi dondur
    return r


def search_bucket(query, max_items=1000):
    """Tek bir yildiz araligi icin, en yuksekten en dusuge repo arar."""
    repos = []
    page = 1
    per_page = 100
    while len(repos) < max_items:
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        }
        r = request_with_retry("GET", SEARCH_URL, params=params)
        if r.status_code != 200:
            break
        data = r.json().get("items", [])
        if not data:
            break
        repos.extend(data)
        page += 1
        if page > 10:  # GitHub'in sabit sinirindan (1000 sonuc) sonra durur
            break
        time.sleep(2)  # arama hiz sinirina (30 istek/dk) takilmamak icin
    return repos[:max_items]


def get_top_repos(n):
    """Butun yildiz araliklarini tarar, sonuclari birlestirir, tekrarlari
    temizler ve en yuksekten en dusuge siralar."""
    merged = {}

    for i, bucket in enumerate(STAR_BUCKETS, start=1):
        print(f"🔍 [{i}/{len(STAR_BUCKETS)}] Taranıyor: {bucket}")
        repos = search_bucket(bucket)
        for repo in repos:
            merged[repo["full_name"]] = repo
        print(f"   -> şu ana kadar toplam {len(merged)} benzersiz repo bulundu")
        if len(merged) >= n:
            break

    print("\n🔍 Son olarak en hareketli (yakın zamanda çok güncellenen) repolar taranıyor...")
    hareketli = search_bucket("stars:>30 pushed:>2026-08-01", max_items=1000)
    for repo in hareketli:
        merged.setdefault(repo["full_name"], repo)

    sonuc = sorted(
        merged.values(),
        key=lambda r: r.get("stargazers_count", 0),
        reverse=True,
    )
    return sonuc[:n]


def watch_repo(owner, name):
    """Tek bir repo icin bildirimleri (watch) acar. Hiz icin onceden
    kontrol yapmiyor, direkt izlemeye alma isteği gönderiyor."""
    url = f"https://api.github.com/repos/{owner}/{name}/subscription"
    payload = {"subscribed": True, "ignored": False}
    r = request_with_retry("PUT", url, json=payload)
    if r.status_code == 200:
        return True, "onaylandı"
    else:
        # Gercek hata mesajini da goster ki sorunu teshis edebilelim
        detay = r.text[:150].replace("\n", " ")
        return False, f"hata {r.status_code} -> {detay}"


def main():
    if TOKEN == "YOUR_GITHUB_TOKEN":
        print("⚠️  Lütfen önce GH_TOKEN secret'ini ayarla!")
        return

    repos = get_top_repos(TOP_N)
    toplam = len(repos)
    print(f"\n📋 Toplam {toplam} benzersiz repo bulundu, en yüksekten en düşüğe işleniyor...\n")

    basarili = 0
    basarisiz = 0

    for i, repo in enumerate(repos, start=1):
        owner = repo["owner"]["login"]
        name = repo["name"]
        stars = repo.get("stargazers_count", "?")
        ok, durum = watch_repo(owner, name)
        if ok:
            basarili += 1
        else:
            basarisiz += 1
        print(f"[{i}/{toplam}] ⭐ {stars} - {owner}/{name} -> {'✅' if ok else '❌'} {durum}")

    print("\n" + "=" * 50)
    print(f"BİTTİ! {basarili} repo onaylandı, {basarisiz} repo başarısız.")
    print("Bu repolarda ileride olacak hareketler için Gmail'ine")
    print("zamanla bildirim gelmeye başlayacak (anında değil).")
    print("=" * 50)


if __name__ == "__main__":
    main()
