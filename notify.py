"""
GITHUB TOPLU BILDIRIM ACMA SCRIPTI (gelismis surum)
=====================================================
Bu script senin bir liste vermene gerek kalmadan, GitHub'daki EN POPULER
ve EN HAREKETLI (en cok konusulan / en cok commit-tartisma alan) public
repolari otomatik olarak bulur ve hepsini "Watch" (izle) durumuna getirir.
Boylece bu repolarda yeni commit, issue, pull request veya tartisma
oldugunda Gmail'ine bildirim e-postasi gelmeye baslar.

NASIL BULUYOR?
- Once en cok yildiz alan (en populer) repolari tarar.
- Sonra son gunlerde en cok guncellenmis / en hareketli repolari tarar
  (yani su an aktif olarak "konusulan", commit atilan projeler).
- Ikisini birlestirip, en yuksekten en dusuge tekrar siralar, TOP_N
  kadarini alir ve hepsinde bildirimi acar.

UYARI: TOP_N sayisi ne kadar yuksek olursa, Gmail'ine o kadar cok
e-posta gelir. 2000 gibi buyuk bir sayida GUNDE BINLERCE e-posta
gelebilir. Istersen TOP_N degerini kucultup tekrar calistirabilirsin.

KULLANIM:
1. TOKEN, GH_TOKEN adinda bir GitHub Actions secret'indan otomatik gelir.
2. TOP_N sayisini asagidan ayarla.
3. Scripti calistir (GitHub Actions -> Run workflow).
"""

import os
import time
import requests

TOKEN = os.environ.get("GH_TOKEN", "YOUR_GITHUB_TOKEN")
TOP_N = 2000  # <-- en yuksekten en asagiya kac repo izlensin

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

SEARCH_URL = "https://api.github.com/search/repositories"


def safe_get(url, params=None, retries=3):
    """Rate limit'e takilirsa biraz bekleyip tekrar dener."""
    for attempt in range(retries):
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 200:
            return r
        if r.status_code == 403 and "rate limit" in r.text.lower():
            print("   ⏳ Hiz siniri asildi, 30 saniye bekleniyor...")
            time.sleep(30)
            continue
        r.raise_for_status()
    return r


def search_repos(query, sort, max_items):
    """Belirtilen kritere gore repo arar, sayfa sayfa gezer."""
    repos = []
    page = 1
    per_page = 100
    while len(repos) < max_items:
        params = {
            "q": query,
            "sort": sort,
            "order": "desc",
            "per_page": per_page,
            "page": page,
        }
        r = safe_get(SEARCH_URL, params=params)
        data = r.json().get("items", [])
        if not data:
            break
        repos.extend(data)
        page += 1
        if page > 10:  # GitHub search API sayfa siniri (guvenlik payi)
            break
    return repos[:max_items]


def get_top_repos(n):
    """
    Iki farkli kaynaktan repo toplar:
    1) En cok yildiz alan (en populer) repolar
    2) Son zamanlarda en cok guncellenen / en hareketli repolar
       (yani su an aktif olarak commit-tartisma alan projeler)
    Ikisini birlestirir, tekrarlari temizler, yildiza gore tekrar
    siralar ve en yuksekten en dusuge n tanesini dondurur.
    """
    print("🔍 En populer repolar taraniyor (yildiz sayisina gore)...")
    populer = search_repos("stars:>100", "stars", n)

    print("🔍 En hareketli / en cok konusulan repolar taraniyor...")
    hareketli = search_repos("stars:>50 pushed:>2026-08-01", "updated", n)

    print("🔗 Sonuclar birlestiriliyor ve tekrarlar temizleniyor...\n")
    merged = {}
    for repo in populer + hareketli:
        full_name = repo["full_name"]
        if full_name not in merged:
            merged[full_name] = repo

    # en yuksekten en dusuge yildiz sayisina gore sirala
    sonuc = sorted(
        merged.values(),
        key=lambda r: r.get("stargazers_count", 0),
        reverse=True,
    )
    return sonuc[:n]


def watch_repo(owner, name):
    """Tek bir repo icin bildirimleri (watch) acar.
    Eger repo zaten izleniyorsa bunu ayri bir durum olarak bildirir."""
    url = f"https://api.github.com/repos/{owner}/{name}/subscription"

    # once zaten izlenip izlenmedigine bak
    kontrol = requests.get(url, headers=HEADERS)
    if kontrol.status_code == 200:
        zaten_veri = kontrol.json()
        if zaten_veri.get("subscribed"):
            return True, "zaten watchlemişsin"

    payload = {"subscribed": True, "ignored": False}
    r = requests.put(url, headers=HEADERS, json=payload)
    if r.status_code == 200:
        return True, "onaylandı"
    else:
        return False, f"hata {r.status_code}"


def main():
    if TOKEN == "YOUR_GITHUB_TOKEN":
        print("⚠️  Lutfen once GH_TOKEN secret'ini ayarla!")
        return

    repos = get_top_repos(TOP_N)
    toplam = len(repos)
    print(f"📋 Toplam {toplam} repo bulundu, en yuksekten en dusuge isleniyor...\n")

    basarili = 0
    basarisiz = 0

    for i, repo in enumerate(repos, start=1):
        owner = repo["owner"]["login"]
        name = repo["name"]
        stars = repo.get("stargazers_count", "?")
        ok, durum = watch_repo(owner, name)
        if ok:
            basarili += 1
            print(f"[{i}/{toplam}] ⭐ {stars} - {owner}/{name} -> ✅ {durum}")
        else:
            basarisiz += 1
            print(f"[{i}/{toplam}] ⭐ {stars} - {owner}/{name} -> ❌ {durum}")

    print("\n" + "=" * 50)
    print(f"BITTI! {basarili} repo onaylandı, {basarisiz} repo basarisiz.")
    print("Artik bu repolardaki hareketler icin Gmail'ine bildirim gelecek.")
    print("=" * 50)


if __name__ == "__main__":
    main()
