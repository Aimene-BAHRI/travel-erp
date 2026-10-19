"""Printable accountant copy rendered exclusively from the immutable confirmation snapshot."""
from django.template import Context, Engine


def render_archive(snapshot):
    payload = snapshot.payload
    rows = []
    for traveler in payload.get('travelers', []):
        rows.append({**traveler, 'charges': [line for line in payload.get('charges', []) if line['traveler_id'] == traveler['id']], 'rooms': [room for room in payload.get('assigned_rooms', []) if room['traveler'] == traveler['id']]})
    template = Engine().from_string('''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>{{ booking.code }} — نسخة المحاسب</title>
<style>body{font:15px Arial,sans-serif;max-width:1000px;margin:30px auto;color:#123}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{border:1px solid #ccd;padding:10px;text-align:right}th{background:#eef5f7}small{word-break:break-all}@media print{button{display:none}body{margin:0}}</style>
<button onclick="window.print()">طباعة / حفظ PDF</button><h1>{{ booking.agency.name }}</h1><h2>نسخة المحاسب · تأكيد الحجز / الفاتورة</h2>
<p>{{ booking.code }} · {{ created }}</p><p>العميل: {{ booking.customer.name }} · {{ booking.trip.name }}</p>
<table><tr><th>المسافر</th><th>الغرف المتفق عليها</th><th>البنود والأسعار</th></tr>{% for traveler in travelers %}<tr><td>{{ traveler.name }}</td><td>{% for room in traveler.rooms %}{{ room.hotel }} / {{ room.room_type }} / {{ room.room }}<br>{% endfor %}</td><td>{% for line in traveler.charges %}{{ line.description }}: {{ line.final_amount }} {{ booking.currency }}<br>{% endfor %}</td></tr>{% endfor %}</table>
<h3>الخدمات الإضافية</h3><table><tr><th>الخدمة</th><th>التفاصيل</th><th>الكمية</th><th>سعر الوحدة</th></tr>{% for item in terms.extras %}<tr><td>{{ item.service }}</td><td>{{ item.description }}</td><td>{{ item.quantity }}</td><td>{{ item.unit_price }} {{ booking.currency }}</td></tr>{% endfor %}</table>
<h2>الإجمالي: {{ booking.total_amount }} {{ booking.currency }}</h2><p>خطة الدفع: {% if terms.payment_plan == 'INSTALLMENTS' %}أقساط{% else %}دفع كامل{% endif %}</p>
{% for item in terms.installments %}<p>{{ item.due_date }}: {{ item.amount }} {{ booking.currency }}</p>{% endfor %}
<p>خطة الدفع ليست إيصال دفع؛ تُسجل الدفعات الفعلية بشكل منفصل.</p><p>{{ terms.notes }}</p><p>المصدر: {{ terms.source }} {{ terms.source_detail }}</p><small>بصمة النسخة المؤرشفة: {{ sha }}</small></html>''')
    return template.render(Context({'booking': payload['booking'], 'travelers': rows, 'terms': payload.get('commercial_details', {}), 'created': snapshot.created_at.isoformat(), 'sha': snapshot.sha256}))
