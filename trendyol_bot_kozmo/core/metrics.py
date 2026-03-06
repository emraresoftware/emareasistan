"""
core.metrics — Performans Metrikleri & Gunluk Rapor
=====================================================
"""

from datetime import datetime, timedelta
from collections import Counter, defaultdict

from config import QUESTION_CATEGORIES, METHOD_LABELS
from core.data import (
    question_log, pending_questions, product_reviews,
)


# ════════════════════════════════════════════════════════
# YORUM DUYGU ANALIZI
# ════════════════════════════════════════════════════════

def get_review_sentiment_stats() -> dict:
    """Yorum duygu analizi istatistikleri."""
    if not product_reviews:
        return {}
    stats = {
        'total': 0,
        'positive': 0,
        'neutral': 0,
        'negative': 0,
        'avg_rate': 0.0,
        'by_product': {},
    }
    total_rate = 0
    for prod_name, reviews in product_reviews.items():
        prod_stats = {'total': 0, 'avg': 0, 'positive': 0,
                      'negative': 0}
        prod_rate_sum = 0
        for rev in reviews:
            rate = rev.get('rate', 0)
            stats['total'] += 1
            total_rate += rate
            prod_stats['total'] += 1
            prod_rate_sum += rate
            if rate >= 4:
                stats['positive'] += 1
                prod_stats['positive'] += 1
            elif rate == 3:
                stats['neutral'] += 1
            else:
                stats['negative'] += 1
                prod_stats['negative'] += 1
        if prod_stats['total'] > 0:
            prod_stats['avg'] = prod_rate_sum / prod_stats['total']
        stats['by_product'][prod_name] = prod_stats
    if stats['total'] > 0:
        stats['avg_rate'] = total_rate / stats['total']
    return stats


# ════════════════════════════════════════════════════════
# PERFORMANS METRIKLERI
# ════════════════════════════════════════════════════════

def get_performance_metrics() -> dict:
    """Gunluk / haftalik performans metriklerini hesapla."""
    now = datetime.now()
    today_str = now.date().isoformat()
    week_start = (now - timedelta(days=now.weekday())).date().isoformat()

    metrics = {
        'total_questions': len(question_log),
        'today_questions': 0,
        'week_questions': 0,
        'auto_resolved': 0,
        'manual_resolved': 0,
        'unresolved': 0,
        'auto_rate': 0.0,
        'category_distribution': defaultdict(int),
        'hourly_distribution': defaultdict(int),
        'daily_distribution': defaultdict(int),
        'method_counts': Counter(),
        'avg_response_methods': {},
    }

    for entry in question_log:
        ts = entry.get('timestamp', '')
        method = entry.get('method', '')
        category = entry.get('category', 'diger')

        metrics['method_counts'][method] += 1
        metrics['category_distribution'][category] += 1

        if ts.startswith(today_str):
            metrics['today_questions'] += 1
        if ts >= week_start:
            metrics['week_questions'] += 1

        try:
            dt = datetime.fromisoformat(ts)
            metrics['hourly_distribution'][dt.hour] += 1
            metrics['daily_distribution'][dt.strftime('%A')] += 1
        except (ValueError, TypeError):
            pass

        if method in ('keyword', 'fuzzy', 'gemini'):
            metrics['auto_resolved'] += 1
        elif method in ('manual_approved', 'manual_edited'):
            metrics['manual_resolved'] += 1
        elif method in ('pending', 'no_match'):
            metrics['unresolved'] += 1

    total = metrics['auto_resolved'] + metrics['manual_resolved']
    if total > 0:
        metrics['auto_rate'] = metrics['auto_resolved'] / total

    return metrics


# ════════════════════════════════════════════════════════
# GUNLUK RAPOR
# ════════════════════════════════════════════════════════

def generate_daily_report() -> str:
    """Gunluk rapor olustur."""
    now = datetime.now()
    today_str = now.date().isoformat()
    today_entries = [e for e in question_log
                     if e.get('timestamp', '').startswith(today_str)]
    total = len(today_entries)
    if total == 0:
        return f"=== Gunluk Rapor — {today_str} ===\n\nBugun soru islenmedi."

    methods = Counter(e.get('method', '') for e in today_entries)
    categories = Counter(e.get('category', 'diger') for e in today_entries)

    auto = (methods.get('keyword', 0) + methods.get('fuzzy', 0)
            + methods.get('gemini', 0))
    manual = (methods.get('manual_approved', 0)
              + methods.get('manual_edited', 0))

    report_lines = [
        f"=== Gunluk Rapor — {today_str} ===",
        "",
        f"Toplam Soru: {total}",
        f"Otomatik Cozulunen: {auto} ({auto/total*100:.0f}%)" if total else "",
        f"Manuel Cozulunen: {manual}",
        f"Bekleyen: {methods.get('pending', 0) + methods.get('no_match', 0)}",
        "",
        "--- Yontem Dagilimi ---",
    ]
    for m, c in methods.most_common():
        report_lines.append(f"  {METHOD_LABELS.get(m, m)}: {c}")

    report_lines.append("")
    report_lines.append("--- Kategori Dagilimi ---")
    for cat, c in categories.most_common():
        cat_info = QUESTION_CATEGORIES.get(cat, {})
        label = cat_info.get('label', cat)
        report_lines.append(f"  {label}: {c}")

    active_pending = [p for p in pending_questions
                      if p.get('status') in ('pending', 'no_match')]
    if active_pending:
        report_lines.append(
            f"\n--- Aktif Bekleyen Sorular: {len(active_pending)} ---")
        for p in active_pending[:5]:
            cat = p.get('category', 'diger')
            cat_label = QUESTION_CATEGORIES.get(cat, {}).get('label', '?')
            report_lines.append(
                f"  • {p.get('question', '')[:60]}... [{cat_label}]")

    return '\n'.join(report_lines)
