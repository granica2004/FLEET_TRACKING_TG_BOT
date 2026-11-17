"""
Дополнения к src/i18n.py:
  FA        — перевод всех текстов на фарси (персидский, Иран);
  DEAL_KEYS — тексты «Мои сделки» и карточки сделки на всех языках;
  STAGES    — понятные клиенту названия стадий сделки.
"""

FA = {
    "lang_choose": "🌐 Выберите язык / Choose language / Tilni tanlang / زبان را انتخاب کنید:",
    "lang_set": "✅ زبان: فارسی",
    "lang_hint": "🌐 تغییر زبان — /language",
    "blocked": "⛔ دسترسی به ربات بسته شده است. لطفاً با دیسپچر تماس بگیرید.",
    "press_start": "برای شروع /start را بزنید",
    "register_first": "❌ ابتدا ثبت‌نام کنید: /start",
    "btn_cancel": "❌ لغو",
    "cancelled": "لغو شد. /start — شروع دوباره.",
    "btn_skip": "رد کردن",
    "btn_yes": "✅ بله",
    "btn_no": "❌ خیر",
    "sent_to_dispatcher": "✉️ پیام شما برای دیسپچر ارسال شد.",
    "msg_from_dispatcher": "✉️ <b>پیام از دیسپچر:</b>\n\n{text}",
    "only_text": "فعلاً فقط پیام متنی پشتیبانی می‌شود.",
    "unnamed": "بدون نام",
    "km": "کیلومتر",
    "msk": "به وقت مسکو",
    "dur_hm": "{h} ساعت {m} دقیقه",
    "dur_m": "{m} دقیقه",
    "ago_now": "همین الان",
    "ago_min": "{n} دقیقه پیش",
    "ago_h": "{n} ساعت پیش",
    "ago_d": "{n} روز پیش",

    "who_are_you": "🚛 <b>ربات ردیابی بار GRANICA 2004</b>\n\nشما چه کسی هستید؟",
    "btn_role_driver": "🚛 من راننده هستم",
    "btn_role_client": "📦 من گیرنده بار هستم",
    "btn_role_broker": "🌍 من فرستنده / کارگزار هستم",

    "consent_text": "🚛 <b>ربات ردیابی حمل‌ونقل GRANICA 2004</b>\n\n"
                    "این ربات موقعیت کامیون را در مسیر ترمینال گمرکی ارسال می‌کند.\n\n"
                    "برای کار، رضایت شما لازم است: در طول سفر، مختصات و نشانی کامیون شما را "
                    "کارگزار گمرکی، فرستنده بار و گیرنده بار می‌بینند. این اطلاعات فقط برای کنترل تحویل "
                    "استفاده می‌شود و فقط در طول سفر فعال ارسال می‌گردد.\n\n"
                    "اگر موافق هستید، دکمه زیر را بزنید:",
    "btn_consent": "✅ با ارسال موقعیت مکانی موافقم",
    "consent_ok": "✅ رضایت ثبت شد. سپاسگزاریم!\n\nاکنون <b>شماره کشنده (کامیون)</b> را بدون فاصله وارد کنید:\n"
                  "مثلاً: 01A123BC یا 60144OBA. اگر کانتینر حمل می‌کنید، می‌توانید شماره کانتینر را وارد کنید.",
    "welcome_back_trip": "👋 خوش آمدید!\n\n🚛 سفر فعال: {truck}\n🏭 ترمینال: {terminal}\n\n"
                         "برای به‌روزرسانی وضعیت، موقعیت خود را ارسال کنید.",
    "welcome_back_new": "👋 خوش آمدید، {name}!\n\nبرای شروع سفر جدید، شماره کشنده را بدون فاصله وارد کنید:",
    "driver_word": "راننده",
    "reg_cancelled": "ثبت‌نام لغو شد. برای شروع /start را بزنید",
    "bad_plate": "❌ قالب شماره نادرست است.\n\nنمونه‌ها:\n• روسیه: А123ВС77\n• خارجی: 60144OBA\n"
                 "• کانتینر: TPPU4000202",
    "reg_done_deal": "✅ <b>ثبت‌نام انجام شد!</b>\n\n🚛 کشنده: {truck}\n\n📋 <b>سفارش:</b>\n{title}\n\n"
                     "🏭 <b>ترمینال مقصد:</b>\n{terminal}\n{address}\n\n"
                     "برای ارسال موقعیت فعلی، دکمه را بزنید.",
    "reg_done_wait": "✅ <b>ثبت‌نام انجام شد!</b>\n\n🚛 کشنده: {truck}\n\n⚠️ <b>سفارش هنوز پیدا نشده است.</b>\n"
                     "وقتی ثبت شود به شما اطلاع می‌دهیم.\n\nتا آن زمان می‌توانید موقعیت خود را ارسال کنید:",
    "attached_to_trip": "✅ <b>شما به سفر متصل شدید</b>\n\n🚛 {truck}\n🏭 ترمینال: {terminal}\n{address}\n"
                        "دکمه «{btn}» را بزنید.",
    "invite_invalid_driver": "لینک نامعتبر است یا سفر به پایان رسیده است. لطفاً با دیسپچر تماس بگیرید.",

    "btn_send_location": "📍 ارسال موقعیت",
    "btn_terminal": "📍 ترمینال مقصد",
    "btn_arrival_date": "📝 تاریخ رسیدن",
    "btn_new_trip": "🔄 سفر جدید",
    "btn_finish": "❌ پایان سفر فعلی",
    "btn_refresh_status": "🔄 به‌روزرسانی وضعیت",
    "btn_start_tracking": "✅ شروع ردیابی",
    "btn_decline": "❌ رد کردن",
    "btn_route_yandex": "🧭 مسیر در Yandex Maps",
    "btn_route_google": "🧭 مسیر در Google Maps",

    "driver_not_found": "❌ خطا: راننده پیدا نشد. /start را بزنید",
    "loc_register_first": "❌ برای ارسال موقعیت ابتدا ثبت‌نام کنید.\n/start را بزنید",
    "loc_saved": "📍 <b>موقعیت ذخیره شد!</b>\n",
    "loc_to_terminal": "\n📏 تا ترمینال: <b>{km} کیلومتر</b>",
    "loc_eta": "⏱️ زمان تخمینی: <b>{eta}</b>",
    "loc_synced": "\n✅ برای کارگزار ارسال شد",
    "loc_sync_err": "\n⚠️ خطا در ارسال اطلاعات به کارگزار",
    "loc_waiting": "\n⏳ در انتظار اتصال به سفارش...",
    "coords": "مختصات: {lat}, {lon}",

    "no_terminal": "❌ ترمینال مقصد در سفارش مشخص نشده است.\nدر همین گفتگو به دیسپچر پیام دهید.",
    "terminal_title": "📍 <b>ترمینال مقصد</b>\n",
    "terminal_no_coords": "\n⚠️ نشانی دقیق ترمینال هنوز ثبت نشده است. از دیسپچر بپرسید — در همین گفتگو پیام بنویسید.",
    "terminal_word": "ترمینال",

    "arrival_ask": "📅 چه زمانی قصد دارید به ترمینال برسید؟",
    "arr_today": "امروز",
    "arr_tomorrow": "فردا",
    "arr_2d": "۲ روز دیگر",
    "arr_3d": "۳ روز دیگر",
    "arr_custom": "📅 وارد کردن تاریخ",
    "arrival_enter_date": "📅 تاریخ رسیدن را به شکل DD.MM.YYYY (میلادی) وارد کنید\nمثلاً: 15.03.2026",
    "arrival_saved": "✅ تاریخ برنامه‌ریزی‌شده رسیدن: <b>{date}</b>\n\nبه کارگزار اطلاع داده شد.",
    "arrival_saved_short": "تاریخ ذخیره شد!",
    "bad_date": "❌ قالب تاریخ نادرست است.\nتاریخ را به شکل DD.MM.YYYY وارد کنید (مثلاً: 15.03.2026)",

    "finish_confirm": "❓ آیا مطمئن هستید که می‌خواهید سفر فعلی را پایان دهید؟",
    "trip_finished": "✅ سفر به پایان رسید!\n\nبرای شروع سفر جدید /start را بزنید",
    "trip_finished_short": "سفر به پایان رسید",
    "tracking_continues": "ردیابی ادامه دارد.",
    "new_trip_enter": "🔄 شروع سفر جدید.\n\nشماره کشنده را بدون فاصله وارد کنید:",
    "no_active_trip": "❌ سفر فعالی وجود ندارد.\nبرای ثبت‌نام /start را بزنید.",
    "deal_found_linked": "✅ <b>سفارش پیدا و متصل شد!</b>\n\n📋 {title}\n🏭 ترمینال: {terminal}\n\n"
                         "اکنون موقعیت شما برای کارگزار ارسال می‌شود.",
    "deal_not_yet": "⏳ هنوز سفارشی برای {truck} ثبت نشده است.\n\nبه ارسال موقعیت ادامه دهید — اطلاعات ذخیره می‌شود.",
    "status": "📋 <b>وضعیت سفر:</b>\n\n🚛 شماره: {truck}\n📦 سفارش: #{deal}\n🏭 ترمینال: {terminal}\n"
              "📅 روزهای در راه: {days}",
    "deal_not_found_short": "❌ سفارش پیدا نشد",
    "tracking_activated": "✅ <b>ردیابی فعال شد!</b>\n\n📋 {title}\n🏭 ترمینال: {terminal}\n\nموقعیت خود را ارسال کنید:",
    "tracking_activated_short": "ردیابی فعال شد!",
    "offer_declined": "رد شد.\nاگر نظرتان تغییر کرد، /start را بزنید",
    "help": "🚛 <b>ربات ردیابی حمل‌ونقل</b>\n\n<b>دستورها:</b>\n/start — شروع / سفر جدید\n"
            "/language — تغییر زبان\n/help — راهنما\n\n<b>دکمه‌ها:</b>\n"
            "📍 ارسال موقعیت — فرستادن موقعیت مکانی\n"
            "📍 ترمینال مقصد — نشانی، نقطه روی نقشه و مسیر در مسیریاب\n"
            "📝 تاریخ رسیدن — تعیین تاریخ برنامه‌ریزی‌شده رسیدن\n"
            "🔄 سفر جدید — شروع سفر تازه\n❌ پایان سفر فعلی — توقف ردیابی\n\n"
            "سؤال از دیسپچر — کافی است در همین گفتگو بنویسید.",

    "morning_request": "🌅 صبح بخیر!\n\nلطفاً برای به‌روزرسانی وضعیت سفر، موقعیت فعلی خود را ارسال کنید.",
    "lastcall_km": "🏁 توجه!\n\nکمتر از {km} کیلومتر تا ترمینال مانده است.\n\nلطفاً تاریخ برنامه‌ریزی‌شده رسیدن را مشخص کنید:",
    "lastcall_days": "🏁 توجه!\n\nبار {days} روز است که در راه است.\n\nلطفاً تاریخ برنامه‌ریزی‌شده رسیدن را مشخص کنید:",
    "dispatcher_asks_location": "📍 دیسپچر از شما می‌خواهد موقعیت فعلی خود را ارسال کنید.\nدکمه «{btn}» را در پایین بزنید.",
    "done_by_stage": "✅ <b>سفر به پایان رسید!</b>\n\nبار به ترمینال رسید. ردیابی متوقف شد.\n\n"
                     "سپاسگزاریم! برای سفر جدید /start را بزنید",
    "done_by_dispatcher": "✅ دیسپچر سفر را به پایان رساند. ردیابی متوقف شد.\nبرای سفر جدید /start را بزنید",
    "deal_matched": "🎉 <b>سفارش پیدا شد!</b>\n\n📋 {title}\n🏭 ترمینال: {terminal}\n\n"
                    "اکنون موقعیت شما برای کارگزار ارسال می‌شود.",
    "bound_by_dispatcher": "✅ <b>سفر شما به سفارش متصل شد</b>\n\n📋 {title}\n🏭 ترمینال: {terminal}\n\n"
                           "اکنون موقعیت شما برای کارگزار ارسال می‌شود.",
    "new_trip_offer": "🚛 <b>سفر جدیدی پیدا شد!</b>\n\n📋 {title}\n🏭 ترمینال: {terminal}\n\nردیابی را شروع کنیم؟",

    "invite_invalid": "لینک نامعتبر است یا قبلاً استفاده شده است. از دیسپچر لینک جدید بخواهید.",
    "joined_manager": "✅ شما به عنوان مدیر متصل شدید. پنل مدیریت — /admin",
    "joined_broker": "✅ شما به عنوان فرستنده / کارگزار متصل شدید.\n\n«{new}» — ایجاد سفر و دریافت لینک برای راننده.\n"
                     "«{my}» — کامیون‌ها اکنون کجا هستند و مسیرشان.",
    "greet": "👋 سلام{who}!\nسفرها: {n}. «{my}» — فهرست.",
    "pending_wait": "⏳ درخواست شما در حال بررسی توسط دیسپچر است. پس از باز شدن دسترسی به شما اطلاع می‌دهیم.",
    "client_phone_ask": "برای نمایش بارهای شما، شماره تلفن خود را به اشتراک بگذارید — با شماره‌ای که به کارگزار "
                        "داده‌اید شما را پیدا می‌کنیم.",
    "broker_phone_ask": "لطفاً شماره تلفن خود را برای تماس به اشتراک بگذارید.",
    "btn_share_phone": "📱 اشتراک شماره تلفن",
    "need_own_phone": "دکمه «{btn}» را بزنید — شماره خود شما لازم است.",
    "client_found": "✅ شما را پیدا کردیم: <b>{name}</b>.\nسفرهای فعلی: {n}. سفرهای جدید سفارش‌های شما خودکار نمایش داده می‌شوند.",
    "client_inn_ask": "این شماره در پایگاه ما پیدا نشد. شناسه مالیاتی روسیه (INN) شرکت خود را وارد کنید (۱۰ یا ۱۲ رقم).",
    "inn_bad": "INN باید ۱۰ یا ۱۲ رقم باشد. دوباره تلاش کنید یا «{btn}» را بزنید.",
    "request_sent": "⏳ درخواست شما برای دیسپچر ارسال شد. پس از باز شدن دسترسی به شما اطلاع می‌دهیم.",
    "broker_company_ask": "نام شرکت و کشور خود را بنویسید (مثلاً: «Sugd Logistics، تاجیکستان»).",
    "company_text_needed": "لطفاً نام شرکت را به صورت متن بنویسید.",
    "btn_my_trips": "📦 سفرهای من",
    "btn_create_trip": "➕ ایجاد سفر",
    "btn_write_dispatcher": "✉️ پیام به دیسپچر",
    "no_trips": "هنوز سفری وجود ندارد. وقتی کامیونی با سفارش شما حرکت کند، اینجا نمایش داده می‌شود.",
    "trips_header": "📦 <b>سفرها</b> ({n}): 🟢 در راه، ⚪ پایان‌یافته در ۳۰ روز گذشته",
    "no_points_short": "بدون نقطه",
    "st_active": "🟢 در راه",
    "st_done": "⚪ پایان‌یافته",
    "st_cancelled": "لغو شده",
    "card_shipment": "📦 ارسال: {d}",
    "card_planned": "📅 رسیدن برنامه‌ریزی‌شده: {d}",
    "card_no_driver": "👤 راننده هنوز متصل نشده است",
    "card_now": "📍 <b>اکنون:</b> {addr}\n🕐 {time} ({ago})",
    "card_dist": "\n📏 تا ترمینال: {km} کیلومتر",
    "card_no_location": "📍 هنوز موقعیتی ارسال نشده است",
    "card_at_terminal": "🏁 از {t} در ترمینال",
    "btn_where": "📍 اکنون کجاست",
    "btn_history": "📜 تاریخچه",
    "btn_map": "🗺 مسیر روی نقشه",
    "btn_refresh": "🔄 به‌روزرسانی",
    "btn_all_trips": "◀️ همه سفرها",
    "btn_open_trip": "🚛 باز کردن سفر",
    "no_access_trip": "به این سفر دسترسی ندارید",
    "no_points": "هنوز نقطه‌ای وجود ندارد",
    "point_ago": "نقطه {ago}",
    "history_header": "📜 <b>تاریخچه {truck}</b> — مجموعاً {n} نقطه، {k} نقطه آخر:\n",
    "history_dist": " · {km} کیلومتر تا ترمینال",
    "new_trip_truck_ask": "شماره کشنده (یا کانتینر) را بدون فاصله وارد کنید:",
    "new_trip_inn_ask": "شناسه مالیاتی روسیه (INN) گیرنده (۱۰ یا ۱۲ رقم) — یا «{btn}»:",
    "inn_or_skip": "INN باید ۱۰ یا ۱۲ رقم باشد، یا «{btn}» را بزنید.",
    "trip_created": "✅ <b>سفر {truck} ایجاد شد</b>",
    "tc_deal_found": "📋 سفارش پیدا شد: {title}\n🏭 {terminal}",
    "tc_deal_not_found": "سفارشی با این شماره هنوز پیدا نشده است — دیسپچر آن را متصل می‌کند.",
    "tc_driver_link": "\n👉 <b>این لینک را برای راننده بفرستید:</b>\n{link}\n\nراننده آن را باز می‌کند، رضایت می‌دهد "
                      "و بلافاصله به این سفر متصل می‌شود — نیازی به وارد کردن شماره نیست.",
    "write_dispatcher_ask": "پیام خود را بنویسید — آن را به دیسپچر می‌رسانم.",
    "access_opened": "✅ دسترسی باز شد. «{my}» — کامیون‌ها اکنون کجا هستند.",
    "access_denied": "متأسفانه دسترسی رد شد. لطفاً با دیسپچر تماس بگیرید.",
    "trip_opened_to_you": "🚛 سفر {truck} برای شما باز شد.",
    "admin_granted": "⭐ پنل مدیریت برای شما باز شد — /admin",
    "admin_revoked": "دسترسی مدیر لغو شد.",

    "ev_started": "🚛 <b>بار در راه است</b>: {title}\nمی‌توانید موقعیت و مسیر کامیون را در همین ربات دنبال کنید.",
    "ev_border": "🛂 <b>کامیون از مرز عبور کرد</b>: {a} ← {b}\n{title}\n📍 {addr}",
    "ev_border_ru": "🛂 <b>کامیون وارد روسیه شد</b>: {a} ← {b}\n{title}\n📍 {addr}",
    "ev_arrived": "🏁 <b>کامیون در ترمینال است</b>: {title}\n📍 {addr}",
    "ev_soon_km": "⏳ <b>به‌زودی می‌رسد</b>: {title} — کمتر از {km} کیلومتر تا ترمینال",
    "ev_soon_days": "⏳ <b>به‌زودی می‌رسد</b>: {title} — {days} روز در راه",
    "ev_done": "✅ <b>سفر به پایان رسید</b>: {title}",

    "cmd_start": "🚛 شروع / سفر جدید",
    "cmd_language": "🌐 زبان",
    "cmd_help": "❓ راهنما",
}

FA_COUNTRIES = {
    "ru": "روسیه", "kz": "قزاقستان", "uz": "ازبکستان", "tj": "تاجیکستان", "kg": "قرقیزستان",
    "tm": "ترکمنستان", "ir": "ایران", "az": "آذربایجان", "ge": "گرجستان", "am": "ارمنستان",
    "by": "بلاروس", "cn": "چین", "tr": "ترکیه", "af": "افغانستان", "mn": "مغولستان",
}

# ---------- «Мои сделки» и карточка сделки ----------
DEAL_KEYS = {
    "btn_my_deals": {"ru": "📋 Мои сделки", "en": "📋 My orders", "uz": "📋 Mening buyurtmalarim",
                     "fa": "📋 سفارش‌های من"},
    "no_deals": {
        "ru": "Сделок за последние 4 месяца нет.",
        "en": "No orders in the last 4 months.",
        "uz": "Oxirgi 4 oyda buyurtmalar yo'q.",
        "fa": "در ۴ ماه گذشته سفارشی وجود ندارد.",
    },
    "deals_header": {
        "ru": "📋 <b>Ваши сделки</b> ({n}) — открытые и за последние 4 месяца:",
        "en": "📋 <b>Your orders</b> ({n}) — open and from the last 4 months:",
        "uz": "📋 <b>Buyurtmalaringiz</b> ({n}) — ochiq va oxirgi 4 oydagilar:",
        "fa": "📋 <b>سفارش‌های شما</b> ({n}) — باز و ۴ ماه گذشته:",
    },
    "deal_stage": {"ru": "📌 Этап: <b>{stage}</b>", "en": "📌 Stage: <b>{stage}</b>",
                   "uz": "📌 Bosqich: <b>{stage}</b>", "fa": "📌 مرحله: <b>{stage}</b>"},
    "deal_terminal": {"ru": "🏭 Терминал: {terminal}", "en": "🏭 Terminal: {terminal}",
                      "uz": "🏭 Terminal: {terminal}", "fa": "🏭 ترمینال: {terminal}"},
    "deal_vehicle": {"ru": "🚛 Транспорт: {truck}", "en": "🚛 Vehicle: {truck}",
                     "uz": "🚛 Transport: {truck}", "fa": "🚛 وسیله نقلیه: {truck}"},
    "deal_shipped": {"ru": "📦 Отгрузка: {d}", "en": "📦 Shipped: {d}", "uz": "📦 Jo'natilgan: {d}",
                     "fa": "📦 ارسال: {d}"},
    "deal_planned": {"ru": "📅 План прибытия: {d}", "en": "📅 Planned arrival: {d}",
                     "uz": "📅 Rejadagi kelish: {d}", "fa": "📅 رسیدن برنامه‌ریزی‌شده: {d}"},
    "deal_arrived": {"ru": "🏁 Прибыл: {d}", "en": "🏁 Arrived: {d}", "uz": "🏁 Yetib keldi: {d}",
                     "fa": "🏁 رسید: {d}"},
    "deal_drivers": {"ru": "\n👤 <b>Водитель</b>", "en": "\n👤 <b>Driver</b>", "uz": "\n👤 <b>Haydovchi</b>",
                     "fa": "\n👤 <b>راننده</b>"},
    "deal_driver_line": {
        "ru": "{name}{contact}\n🚛 {truck} · последняя точка: {seen}",
        "en": "{name}{contact}\n🚛 {truck} · last point: {seen}",
        "uz": "{name}{contact}\n🚛 {truck} · oxirgi nuqta: {seen}",
        "fa": "{name}{contact}\n🚛 {truck} · آخرین نقطه: {seen}",
    },
    "deal_driver_phone": {"ru": "📞 Телефон водителя: {phone}", "en": "📞 Driver's phone: {phone}",
                          "uz": "📞 Haydovchi telefoni: {phone}", "fa": "📞 تلفن راننده: {phone}"},
    "deal_no_driver": {
        "ru": "Водитель пока не подключён к боту.",
        "en": "The driver has not connected to the bot yet.",
        "uz": "Haydovchi hali botga ulanmagan.",
        "fa": "راننده هنوز به ربات متصل نشده است.",
    },
    "deal_comments": {"ru": "\n💬 <b>Комментарии менеджера:</b>\n{text}",
                      "en": "\n💬 <b>Manager's notes:</b>\n{text}",
                      "uz": "\n💬 <b>Menejer izohlari:</b>\n{text}",
                      "fa": "\n💬 <b>یادداشت‌های مدیر:</b>\n{text}"},
    "deal_subject": {
        "ru": "\n✉️ <b>Тема письма</b> — указывайте её в переписке с нами (нажмите, чтобы скопировать):\n<code>{subject}</code>",
        "en": "\n✉️ <b>Email subject</b> — use it when you email us (tap to copy):\n<code>{subject}</code>",
        "uz": "\n✉️ <b>Xat mavzusi</b> — biz bilan yozishmada ishlating (nusxalash uchun bosing):\n<code>{subject}</code>",
        "fa": "\n✉️ <b>موضوع ایمیل</b> — هنگام مکاتبه با ما از آن استفاده کنید (برای کپی بزنید):\n<code>{subject}</code>",
    },
    "btn_copy_subject": {"ru": "📋 Скопировать тему письма", "en": "📋 Copy email subject",
                         "uz": "📋 Xat mavzusini nusxalash", "fa": "📋 کپی موضوع ایمیل"},
    "btn_deal": {"ru": "📋 Сделка", "en": "📋 Order", "uz": "📋 Buyurtma", "fa": "📋 سفارش"},
    "btn_all_deals": {"ru": "◀️ Все сделки", "en": "◀️ All orders", "uz": "◀️ Barcha buyurtmalar",
                      "fa": "◀️ همه سفارش‌ها"},
    "btn_driver_chat": {"ru": "💬 Написать водителю в Telegram", "en": "💬 Message the driver on Telegram",
                        "uz": "💬 Haydovchiga Telegramda yozish", "fa": "💬 پیام به راننده در تلگرام"},
    "no_access_deal": {"ru": "Нет доступа к этой сделке", "en": "No access to this order",
                       "uz": "Bu buyurtmaga ruxsat yo'q", "fa": "به این سفارش دسترسی ندارید"},
    "deal_load_error": {"ru": "Не удалось загрузить сделку, попробуйте позже",
                        "en": "Could not load the order, please try later",
                        "uz": "Buyurtmani yuklab bo'lmadi, keyinroq urinib ko'ring",
                        "fa": "بارگیری سفارش ممکن نشد، بعداً دوباره تلاش کنید"},
}

# Понятные клиенту названия стадий (ID стадии в Битриксе → текст)
STAGES = {
    "NEW": {"ru": "подготовка документов", "en": "preparing documents", "uz": "hujjatlar tayyorlanmoqda",
            "fa": "آماده‌سازی مدارک"},
    "UC_SDO64X": {"ru": "груз в пути", "en": "cargo on the way", "uz": "yuk yo'lda", "fa": "بار در راه است"},
    "9": {"ru": "груз прибыл на терминал", "en": "cargo arrived at the terminal", "uz": "yuk terminalga yetib keldi",
          "fa": "بار به ترمینال رسید"},
    "UC_0FYZY9": {"ru": "груз оформлен", "en": "customs cleared", "uz": "yuk rasmiylashtirildi",
                  "fa": "ترخیص گمرکی انجام شد"},
    "UC_9G2PZA": {"ru": "груз оформлен", "en": "customs cleared", "uz": "yuk rasmiylashtirildi",
                  "fa": "ترخیص گمرکی انجام شد"},
    "5": {"ru": "дополнительная проверка", "en": "additional check", "uz": "qo'shimcha tekshiruv",
          "fa": "بررسی تکمیلی"},
    "1": {"ru": "финальный счёт", "en": "final invoice", "uz": "yakuniy hisob", "fa": "صورت‌حساب نهایی"},
    "WON": {"ru": "завершена", "en": "completed", "uz": "yakunlandi", "fa": "تکمیل شد"},
    "LOSE": {"ru": "отменена", "en": "cancelled", "uz": "bekor qilindi", "fa": "لغو شد"},
}
