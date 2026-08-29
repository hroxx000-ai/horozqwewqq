"""
Bu script senin bir liste vermene gerek kalmadan, GitHub'daki EN POPÜLER /
EN AKTİF public repoları otomatik olarak bulur (yıldız sayısına göre en
yüksekten en düşüğe sıralar) ve hepsini "Watch" (izle) durumuna getirir.
Böylece Apple gibi büyük ve çok hareketli repolar dahil, en çok konuşulan
projelerin commit / tartışma bildirimlerini Gmail'ine almaya başlarsın.

UYARI: Çok popüler repoları (Apple'ın Swift'i gibi) izlemek GÜNDE YÜZLERCE
e-posta demek olabilir. TOP_N sayısını küçük tutarak (örn. 20-30) başlamanı
öneririm, istersen sonra artırırsın.

KULLANIM:
1. Aşağıdaki YOUR_GITHUB_TOKEN kısmına kendi (yeni) token'ını yaz.
2. TOP_N sayısını istediğin gibi ayarla (kaç repo izlensin).
3. Scripti çalıştır.
"""

import requests

import os

TOKEN = os.environ.get("GH_TOKEN", "YOUR_GITHUB_TOKEN")  # token GitHub Actions secret'ından gelir
TOP_N = 300                   # <-- yen yüksekten en aşağıya kaç repo izlensin


HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def get_top_repos(n):
    """GitHub genelinde en çok yıldız alan (en popüler/en aktif) repoları,
    en yüksekten en düşüğe sıralı şekilde getirir."""
    repos = []
    page = 1
    per_page = 100
    while len(repos) < n:
        url = (
            "https://api.github.com/search/repositories"
            f"?q=stars:%3E1&sort=stars&order=desc&per_page={per_page}&page={page}"
        )
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json().get("items", [])
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos[:n]


def watch_repo(owner, name):
    """Tek bir repo için bildirimleri (watch) açar."""
    url = f"https://api.github.com/repos/{owner}/{name}/subscription"
    payload = {"subscribed": True, "ignored": False}
    r = requests.put(url, headers=HEADERS, json=payload)
    if r.status_code == 200:
        print(f"✅ {owner}/{name} -> bildirimler açıldı")
    else:
        print(f"❌ {owner}/{name} -> hata: {r.status_code} {r.text}")


def main():
    if TOKEN == "YOUR_GITHUB_TOKEN":
        print("Lütfen önce TOKEN değişkenine kendi GitHub token'ını yapıştır!")
        return

    repos = get_top_repos(TOP_N)
    print(f"En popüler {len(repos)} repo bulundu, en yüksekten en düşüğe işleniyor...\n")

    for i, repo in enumerate(repos, start=1):
        owner = repo["owner"]["login"]
        name = repo["name"]
        stars = repo.get("stargazers_count", "?")
        print(f"[{i}/{len(repos)}] ⭐ {stars} - {owner}/{name}")
        watch_repo(owner, name)

    print("\nBitti! Artık en popüler repolarda bildirim açık.")


if __name__ == "__main__":
    main()
