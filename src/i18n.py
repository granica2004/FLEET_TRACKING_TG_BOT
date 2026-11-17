"""
Переводы интерфейса водителя, клиента и брокера: ru, en, uz (узбекский, латиница).
Админка и комментарии в Битриксе — только на русском.

t(lang, key, **kw) — текст; V(key) — все варианты кнопки (для фильтров по тексту).
Язык пользователя хранится в таблице user_prefs; до выбора — угадывается по language_code Telegram.
"""

from typing import Dict, Optional, Set

LANGS = ("ru", "en", "uz")
DEFAULT = "ru"
LANG_NAMES = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "uz": "🇺🇿 O'zbekcha"}

T: Dict[str, Dict[str, str]] = {
    # ---------- общее ----------
    "lang_choose": {
        "ru": "🌐 Выберите язык / Choose language / Tilni tanlang:",
        "en": "🌐 Выберите язык / Choose language / Tilni tanlang:",
        "uz": "🌐 Выберите язык / Choose language / Tilni tanlang:",
    },
    "lang_set": {"ru": "✅ Язык: Русский", "en": "✅ Language: English", "uz": "✅ Til: O'zbekcha"},
    "lang_hint": {
        "ru": "🌐 Сменить язык — /language",
        "en": "🌐 Change language — /language",
        "uz": "🌐 Tilni o'zgartirish — /language",
    },
    "blocked": {
        "ru": "⛔ Доступ к боту закрыт. Обратитесь к диспетчеру.",
        "en": "⛔ Access to the bot is closed. Please contact the dispatcher.",
        "uz": "⛔ Botga kirish yopilgan. Dispetcherga murojaat qiling.",
    },
    "press_start": {
        "ru": "Для начала работы нажмите /start",
        "en": "Press /start to begin",
        "uz": "Boshlash uchun /start tugmasini bosing",
    },
    "register_first": {
        "ru": "❌ Сначала зарегистрируйтесь: /start",
        "en": "❌ Please register first: /start",
        "uz": "❌ Avval ro'yxatdan o'ting: /start",
    },
    "btn_cancel": {"ru": "❌ Отмена", "en": "❌ Cancel", "uz": "❌ Bekor qilish"},
    "cancelled": {
        "ru": "Отменено. /start — начать заново.",
        "en": "Cancelled. /start — start over.",
        "uz": "Bekor qilindi. /start — qaytadan boshlash.",
    },
    "btn_skip": {"ru": "Пропустить", "en": "Skip", "uz": "O'tkazib yuborish"},
    "btn_yes": {"ru": "✅ Да", "en": "✅ Yes", "uz": "✅ Ha"},
    "btn_no": {"ru": "❌ Нет", "en": "❌ No", "uz": "❌ Yo'q"},
    "sent_to_dispatcher": {
        "ru": "✉️ Сообщение передано диспетчеру.",
        "en": "✉️ Your message has been sent to the dispatcher.",
        "uz": "✉️ Xabaringiz dispetcherga yuborildi.",
    },
    "msg_from_dispatcher": {
        "ru": "✉️ <b>Сообщение от диспетчера:</b>\n\n{text}",
        "en": "✉️ <b>Message from the dispatcher:</b>\n\n{text}",
        "uz": "✉️ <b>Dispetcherdan xabar:</b>\n\n{text}",
    },
    "only_text": {
        "ru": "Пока можно отправить только текст.",
        "en": "Only text messages are supported for now.",
        "uz": "Hozircha faqat matn yuborish mumkin.",
    },
    "unnamed": {"ru": "Без названия", "en": "Untitled", "uz": "Nomsiz"},
    "km": {"ru": "км", "en": "km", "uz": "km"},
    "msk": {"ru": "МСК", "en": "Moscow time", "uz": "Moskva vaqti"},
    "dur_hm": {"ru": "{h} ч {m} мин", "en": "{h} h {m} min", "uz": "{h} soat {m} daqiqa"},
    "dur_m": {"ru": "{m} мин", "en": "{m} min", "uz": "{m} daqiqa"},
    "ago_now": {"ru": "только что", "en": "just now", "uz": "hozirgina"},
    "ago_min": {"ru": "{n} мин назад", "en": "{n} min ago", "uz": "{n} daqiqa oldin"},
    "ago_h": {"ru": "{n} ч назад", "en": "{n} h ago", "uz": "{n} soat oldin"},
    "ago_d": {"ru": "{n} дн назад", "en": "{n} d ago", "uz": "{n} kun oldin"},

    # ---------- выбор роли ----------
    "who_are_you": {
        "ru": "🚛 <b>Бот отслеживания грузов ГРАНИЦА 2004</b>\n\nКто вы?",
        "en": "🚛 <b>GRANICA 2004 cargo tracking bot</b>\n\nWho are you?",
        "uz": "🚛 <b>GRANICA 2004 yuklarni kuzatish boti</b>\n\nSiz kimsiz?",
    },
    "btn_role_driver": {"ru": "🚛 Я водитель", "en": "🚛 I am a driver", "uz": "🚛 Men haydovchiman"},
    "btn_role_client": {
        "ru": "📦 Я получатель груза", "en": "📦 I am the consignee", "uz": "📦 Men yuk qabul qiluvchiman",
    },
    "btn_role_broker": {
        "ru": "🌍 Я отправитель / брокер", "en": "🌍 I am a shipper / broker",
        "uz": "🌍 Men jo'natuvchi / brokerman",
    },

    # ---------- водитель: регистрация ----------
    "consent_text": {
        "ru": "🚛 <b>Бот отслеживания перевозок ГРАНИЦА 2004</b>\n\n"
              "Бот передаёт местоположение машины на пути к таможенному терминалу.\n\n"
              "Для работы нужно ваше согласие: координаты и адрес вашей машины во время рейса увидят "
              "таможенный брокер, отправитель груза и получатель груза. Данные используются только "
              "для контроля доставки и передаются только во время активного рейса.\n\n"
              "Нажмите кнопку ниже, если согласны:",
        "en": "🚛 <b>GRANICA 2004 transport tracking bot</b>\n\n"
              "The bot shares the truck's location on the way to the customs terminal.\n\n"
              "Your consent is required: during the trip, the coordinates and address of your truck will be "
              "visible to the customs broker, the shipper and the consignee. The data is used only to monitor "
              "the delivery and is shared only during an active trip.\n\n"
              "Press the button below if you agree:",
        "uz": "🚛 <b>GRANICA 2004 tashuvlarni kuzatish boti</b>\n\n"
              "Bot bojxona terminaliga ketayotgan mashinaning joylashuvini yuboradi.\n\n"
              "Buning uchun roziligingiz kerak: reys davomida mashinangiz koordinatalari va manzilini "
              "bojxona brokeri, yuk jo'natuvchi va yuk qabul qiluvchi ko'radi. Ma'lumotlar faqat yetkazib "
              "berishni nazorat qilish uchun ishlatiladi va faqat faol reys davomida uzatiladi.\n\n"
              "Rozi bo'lsangiz, quyidagi tugmani bosing:",
    },
    "btn_consent": {
        "ru": "✅ Даю согласие на передачу геолокации",
        "en": "✅ I agree to share my location",
        "uz": "✅ Joylashuvni yuborishga roziman",
    },
    "consent_ok": {
        "ru": "✅ Согласие получено! Спасибо.\n\nТеперь введите <b>номер тягача</b> (без пробелов):\n"
              "Например: А123ВС77 или 60144OBA. Если везёте контейнер — можно номер контейнера.",
        "en": "✅ Consent received. Thank you!\n\nNow enter the <b>truck (tractor) number</b> without spaces:\n"
              "For example: 01A123BC or 60144OBA. If you carry a container, you can enter the container number.",
        "uz": "✅ Rozilik olindi. Rahmat!\n\nEndi <b>tyagach raqamini</b> probelsiz kiriting:\n"
              "Masalan: 01A123BC yoki 60144OBA. Konteyner olib ketayotgan bo'lsangiz, konteyner raqamini "
              "kiritishingiz mumkin.",
    },
    "welcome_back_trip": {
        "ru": "👋 С возвращением!\n\n🚛 Активный рейс: {truck}\n🏭 Терминал: {terminal}\n\n"
              "Отправьте своё местоположение для обновления статуса.",
        "en": "👋 Welcome back!\n\n🚛 Active trip: {truck}\n🏭 Terminal: {terminal}\n\n"
              "Send your location to update the status.",
        "uz": "👋 Xush kelibsiz!\n\n🚛 Faol reys: {truck}\n🏭 Terminal: {terminal}\n\n"
              "Holatni yangilash uchun joylashuvingizni yuboring.",
    },
    "welcome_back_new": {
        "ru": "👋 С возвращением, {name}!\n\nВведите номер тягача для начала новой перевозки (без пробелов):",
        "en": "👋 Welcome back, {name}!\n\nEnter the truck number to start a new trip (without spaces):",
        "uz": "👋 Xush kelibsiz, {name}!\n\nYangi reysni boshlash uchun tyagach raqamini kiriting (probelsiz):",
    },
    "driver_word": {"ru": "водитель", "en": "driver", "uz": "haydovchi"},
    "reg_cancelled": {
        "ru": "Регистрация отменена. Для начала нажмите /start",
        "en": "Registration cancelled. Press /start to begin",
        "uz": "Ro'yxatdan o'tish bekor qilindi. Boshlash uchun /start bosing",
    },
    "bad_plate": {
        "ru": "❌ Неверный формат номера.\n\nПримеры:\n• Российский: А123ВС77\n• Иностранный: 60144OBA\n"
              "• Контейнер: TPPU4000202",
        "en": "❌ Invalid number format.\n\nExamples:\n• Russian: А123ВС77\n• Foreign: 60144OBA\n"
              "• Container: TPPU4000202",
        "uz": "❌ Raqam formati noto'g'ri.\n\nMisollar:\n• Rossiya: А123ВС77\n• Xorijiy: 60144OBA\n"
              "• Konteyner: TPPU4000202",
    },
    "reg_done_deal": {
        "ru": "✅ <b>Регистрация завершена!</b>\n\n🚛 Тягач: {truck}\n\n📋 <b>Заказ:</b>\n{title}\n\n"
              "🏭 <b>Терминал назначения:</b>\n{terminal}\n{address}\n\n"
              "Нажмите кнопку для отправки текущего местоположения.",
        "en": "✅ <b>Registration complete!</b>\n\n🚛 Truck: {truck}\n\n📋 <b>Order:</b>\n{title}\n\n"
              "🏭 <b>Destination terminal:</b>\n{terminal}\n{address}\n\n"
              "Press the button to send your current location.",
        "uz": "✅ <b>Ro'yxatdan o'tish yakunlandi!</b>\n\n🚛 Tyagach: {truck}\n\n📋 <b>Buyurtma:</b>\n{title}\n\n"
              "🏭 <b>Manzil terminali:</b>\n{terminal}\n{address}\n\n"
              "Joriy joylashuvni yuborish uchun tugmani bosing.",
    },
    "reg_done_wait": {
        "ru": "✅ <b>Регистрация завершена!</b>\n\n🚛 Тягач: {truck}\n\n⚠️ <b>Заказ пока не найден.</b>\n"
              "Вы получите уведомление, когда он появится.\n\nПока можете отправлять своё местоположение:",
        "en": "✅ <b>Registration complete!</b>\n\n🚛 Truck: {truck}\n\n⚠️ <b>The order has not been found yet.</b>\n"
              "You will be notified when it appears.\n\nMeanwhile you can send your location:",
        "uz": "✅ <b>Ro'yxatdan o'tish yakunlandi!</b>\n\n🚛 Tyagach: {truck}\n\n⚠️ <b>Buyurtma hali topilmadi.</b>\n"
              "U paydo bo'lganda sizga xabar beramiz.\n\nHozircha joylashuvingizni yuborishingiz mumkin:",
    },
    "attached_to_trip": {
        "ru": "✅ <b>Вы подключены к рейсу</b>\n\n🚛 {truck}\n🏭 Терминал: {terminal}\n{address}\n"
              "Нажмите «{btn}».",
        "en": "✅ <b>You are connected to the trip</b>\n\n🚛 {truck}\n🏭 Terminal: {terminal}\n{address}\n"
              "Press «{btn}».",
        "uz": "✅ <b>Siz reysga ulandingiz</b>\n\n🚛 {truck}\n🏭 Terminal: {terminal}\n{address}\n"
              "«{btn}» tugmasini bosing.",
    },
    "invite_invalid_driver": {
        "ru": "Ссылка недействительна или рейс уже завершён. Обратитесь к диспетчеру.",
        "en": "The link is invalid or the trip has already ended. Please contact the dispatcher.",
        "uz": "Havola yaroqsiz yoki reys allaqachon tugagan. Dispetcherga murojaat qiling.",
    },

    # ---------- водитель: кнопки ----------
    "btn_send_location": {
        "ru": "📍 Отправить местоположение", "en": "📍 Send location", "uz": "📍 Joylashuvni yuborish",
    },
    "btn_terminal": {"ru": "📍 Терминал прибытия", "en": "📍 Arrival terminal", "uz": "📍 Kelish terminali"},
    "btn_arrival_date": {"ru": "📝 Дата прибытия", "en": "📝 Arrival date", "uz": "📝 Kelish sanasi"},
    "btn_new_trip": {"ru": "🔄 Новая перевозка", "en": "🔄 New trip", "uz": "🔄 Yangi reys"},
    "btn_finish": {"ru": "❌ Завершить текущую", "en": "❌ Finish current trip", "uz": "❌ Joriy reysni tugatish"},
    "btn_refresh_status": {"ru": "🔄 Обновить статус", "en": "🔄 Refresh status", "uz": "🔄 Holatni yangilash"},
    "btn_start_tracking": {
        "ru": "✅ Начать отслеживание", "en": "✅ Start tracking", "uz": "✅ Kuzatishni boshlash",
    },
    "btn_decline": {"ru": "❌ Отклонить", "en": "❌ Decline", "uz": "❌ Rad etish"},
    "btn_route_yandex": {
        "ru": "🧭 Маршрут в Яндекс Картах", "en": "🧭 Route in Yandex Maps", "uz": "🧭 Yandex Xaritada yo'nalish",
    },
    "btn_route_google": {
        "ru": "🧭 Маршрут в Google Maps", "en": "🧭 Route in Google Maps", "uz": "🧭 Google Mapsda yo'nalish",
    },

    # ---------- водитель: геолокация ----------
    "driver_not_found": {
        "ru": "❌ Ошибка: водитель не найден. Нажмите /start",
        "en": "❌ Error: driver not found. Press /start",
        "uz": "❌ Xato: haydovchi topilmadi. /start bosing",
    },
    "loc_register_first": {
        "ru": "❌ Для отправки геолокации сначала зарегистрируйтесь.\nНажмите /start",
        "en": "❌ Please register before sending your location.\nPress /start",
        "uz": "❌ Joylashuvni yuborish uchun avval ro'yxatdan o'ting.\n/start bosing",
    },
    "loc_saved": {"ru": "📍 <b>Локация сохранена!</b>\n", "en": "📍 <b>Location saved!</b>\n",
                  "uz": "📍 <b>Joylashuv saqlandi!</b>\n"},
    "loc_to_terminal": {
        "ru": "\n📏 До терминала: <b>{km} км</b>", "en": "\n📏 To the terminal: <b>{km} km</b>",
        "uz": "\n📏 Terminalgacha: <b>{km} km</b>",
    },
    "loc_eta": {"ru": "⏱️ Расчётное время: <b>{eta}</b>", "en": "⏱️ Estimated time: <b>{eta}</b>",
                "uz": "⏱️ Taxminiy vaqt: <b>{eta}</b>"},
    "loc_synced": {"ru": "\n✅ Данные отправлены брокеру", "en": "\n✅ Sent to the broker",
                   "uz": "\n✅ Ma'lumotlar brokerga yuborildi"},
    "loc_sync_err": {"ru": "\n⚠️ Ошибка передачи данных брокеру", "en": "\n⚠️ Failed to send data to the broker",
                     "uz": "\n⚠️ Ma'lumotlarni brokerga yuborishda xato"},
    "loc_waiting": {"ru": "\n⏳ Ожидание привязки к заказу...", "en": "\n⏳ Waiting to be linked to an order...",
                    "uz": "\n⏳ Buyurtmaga bog'lanish kutilmoqda..."},
    "coords": {"ru": "Координаты: {lat}, {lon}", "en": "Coordinates: {lat}, {lon}", "uz": "Koordinatalar: {lat}, {lon}"},

    # ---------- водитель: терминал ----------
    "no_terminal": {
        "ru": "❌ Терминал назначения не указан в заказе.\nНапишите диспетчеру прямо в этот чат.",
        "en": "❌ The destination terminal is not specified in the order.\nWrite to the dispatcher in this chat.",
        "uz": "❌ Buyurtmada manzil terminali ko'rsatilmagan.\nDispetcherga shu chatda yozing.",
    },
    "terminal_title": {"ru": "📍 <b>Терминал прибытия</b>\n", "en": "📍 <b>Arrival terminal</b>\n",
                       "uz": "📍 <b>Kelish terminali</b>\n"},
    "terminal_no_coords": {
        "ru": "\n⚠️ Точный адрес терминала пока не внесён. Уточните у диспетчера — напишите сообщение прямо в этот чат.",
        "en": "\n⚠️ The exact terminal address has not been added yet. Ask the dispatcher — write a message in this chat.",
        "uz": "\n⚠️ Terminalning aniq manzili hali kiritilmagan. Dispetcherdan so'rang — shu chatda xabar yozing.",
    },
    "terminal_word": {"ru": "Терминал", "en": "Terminal", "uz": "Terminal"},

    # ---------- водитель: дата прибытия ----------
    "arrival_ask": {"ru": "📅 Когда планируете прибыть на терминал?", "en": "📅 When do you plan to arrive at the terminal?",
                    "uz": "📅 Terminalga qachon yetib kelishni rejalashtiryapsiz?"},
    "arr_today": {"ru": "Сегодня", "en": "Today", "uz": "Bugun"},
    "arr_tomorrow": {"ru": "Завтра", "en": "Tomorrow", "uz": "Ertaga"},
    "arr_2d": {"ru": "Через 2 дня", "en": "In 2 days", "uz": "2 kundan keyin"},
    "arr_3d": {"ru": "Через 3 дня", "en": "In 3 days", "uz": "3 kundan keyin"},
    "arr_custom": {"ru": "📅 Указать дату", "en": "📅 Enter a date", "uz": "📅 Sanani kiritish"},
    "arrival_enter_date": {
        "ru": "📅 Введите дату прибытия в формате ДД.ММ.ГГГГ\nНапример: 15.03.2026",
        "en": "📅 Enter the arrival date as DD.MM.YYYY\nFor example: 15.03.2026",
        "uz": "📅 Kelish sanasini KK.OO.YYYY formatida kiriting\nMasalan: 15.03.2026",
    },
    "arrival_saved": {
        "ru": "✅ Планируемая дата прибытия: <b>{date}</b>\n\nИнформация передана брокеру.",
        "en": "✅ Planned arrival date: <b>{date}</b>\n\nThe broker has been informed.",
        "uz": "✅ Rejalashtirilgan kelish sanasi: <b>{date}</b>\n\nMa'lumot brokerga yuborildi.",
    },
    "arrival_saved_short": {"ru": "Дата сохранена!", "en": "Date saved!", "uz": "Sana saqlandi!"},
    "bad_date": {
        "ru": "❌ Неверный формат даты.\nВведите дату в формате ДД.ММ.ГГГГ (например: 15.03.2026)",
        "en": "❌ Invalid date format.\nEnter the date as DD.MM.YYYY (for example: 15.03.2026)",
        "uz": "❌ Sana formati noto'g'ri.\nSanani KK.OO.YYYY formatida kiriting (masalan: 15.03.2026)",
    },

    # ---------- водитель: завершение, статус ----------
    "finish_confirm": {"ru": "❓ Вы уверены, что хотите завершить текущую перевозку?",
                       "en": "❓ Are you sure you want to finish the current trip?",
                       "uz": "❓ Joriy reysni tugatmoqchimisiz?"},
    "trip_finished": {"ru": "✅ Перевозка завершена!\n\nДля начала новой перевозки нажмите /start",
                      "en": "✅ The trip is finished!\n\nPress /start to begin a new trip",
                      "uz": "✅ Reys tugadi!\n\nYangi reys uchun /start bosing"},
    "trip_finished_short": {"ru": "Перевозка завершена", "en": "Trip finished", "uz": "Reys tugadi"},
    "tracking_continues": {"ru": "Отслеживание продолжается.", "en": "Tracking continues.",
                           "uz": "Kuzatish davom etmoqda."},
    "new_trip_enter": {"ru": "🔄 Начинаем новую перевозку.\n\nВведите номер тягача (без пробелов):",
                       "en": "🔄 Starting a new trip.\n\nEnter the truck number (without spaces):",
                       "uz": "🔄 Yangi reysni boshlaymiz.\n\nTyagach raqamini kiriting (probelsiz):"},
    "no_active_trip": {"ru": "❌ Нет активной перевозки.\nНажмите /start для регистрации.",
                       "en": "❌ No active trip.\nPress /start to register.",
                       "uz": "❌ Faol reys yo'q.\nRo'yxatdan o'tish uchun /start bosing."},
    "deal_found_linked": {
        "ru": "✅ <b>Заказ найден и привязан!</b>\n\n📋 {title}\n🏭 Терминал: {terminal}\n\n"
              "Теперь ваше местоположение передаётся брокеру.",
        "en": "✅ <b>Order found and linked!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\n"
              "Your location is now shared with the broker.",
        "uz": "✅ <b>Buyurtma topildi va bog'landi!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\n"
              "Endi joylashuvingiz brokerga yuboriladi.",
    },
    "deal_not_yet": {
        "ru": "⏳ Заказ для номера {truck} пока не создан.\n\nПродолжайте отправлять геолокацию — данные сохраняются.",
        "en": "⏳ No order for {truck} yet.\n\nKeep sending your location — the data is saved.",
        "uz": "⏳ {truck} raqami uchun buyurtma hali yaratilmagan.\n\nJoylashuvni yuborishda davom eting — "
              "ma'lumotlar saqlanadi.",
    },
    "status": {
        "ru": "📋 <b>Статус перевозки:</b>\n\n🚛 Номер: {truck}\n📦 Заказ: #{deal}\n🏭 Терминал: {terminal}\n"
              "📅 Дней в пути: {days}",
        "en": "📋 <b>Trip status:</b>\n\n🚛 Number: {truck}\n📦 Order: #{deal}\n🏭 Terminal: {terminal}\n"
              "📅 Days on the road: {days}",
        "uz": "📋 <b>Reys holati:</b>\n\n🚛 Raqam: {truck}\n📦 Buyurtma: #{deal}\n🏭 Terminal: {terminal}\n"
              "📅 Yo'ldagi kunlar: {days}",
    },
    "deal_not_found_short": {"ru": "❌ Заказ не найден", "en": "❌ Order not found", "uz": "❌ Buyurtma topilmadi"},
    "tracking_activated": {
        "ru": "✅ <b>Отслеживание активировано!</b>\n\n📋 {title}\n🏭 Терминал: {terminal}\n\nОтправьте своё местоположение:",
        "en": "✅ <b>Tracking activated!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\nSend your location:",
        "uz": "✅ <b>Kuzatish yoqildi!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\nJoylashuvingizni yuboring:",
    },
    "tracking_activated_short": {"ru": "Отслеживание активировано!", "en": "Tracking activated!",
                                 "uz": "Kuzatish yoqildi!"},
    "offer_declined": {"ru": "Уведомление отклонено.\nЕсли передумаете — нажмите /start",
                       "en": "Declined.\nIf you change your mind, press /start",
                       "uz": "Rad etildi.\nFikringizni o'zgartirsangiz, /start bosing"},
    "help": {
        "ru": "🚛 <b>Бот отслеживания перевозок</b>\n\n<b>Команды:</b>\n/start — начать работу / новая перевозка\n"
              "/language — сменить язык\n/help — справка\n\n<b>Кнопки:</b>\n"
              "📍 Отправить местоположение — передать геолокацию\n"
              "📍 Терминал прибытия — адрес, точка на карте и маршрут в навигаторе\n"
              "📝 Дата прибытия — указать планируемую дату прибытия\n"
              "🔄 Новая перевозка — начать новый рейс\n❌ Завершить текущую — завершить отслеживание\n\n"
              "Вопрос диспетчеру — просто напишите его в этот чат.",
        "en": "🚛 <b>Transport tracking bot</b>\n\n<b>Commands:</b>\n/start — start / new trip\n"
              "/language — change language\n/help — help\n\n<b>Buttons:</b>\n"
              "📍 Send location — share your location\n"
              "📍 Arrival terminal — address, map pin and route in a navigator\n"
              "📝 Arrival date — set the planned arrival date\n"
              "🔄 New trip — start a new trip\n❌ Finish current trip — stop tracking\n\n"
              "Questions for the dispatcher — just write them in this chat.",
        "uz": "🚛 <b>Tashuvlarni kuzatish boti</b>\n\n<b>Buyruqlar:</b>\n/start — boshlash / yangi reys\n"
              "/language — tilni o'zgartirish\n/help — yordam\n\n<b>Tugmalar:</b>\n"
              "📍 Joylashuvni yuborish — geolokatsiyani yuborish\n"
              "📍 Kelish terminali — manzil, xaritadagi nuqta va navigatordagi yo'nalish\n"
              "📝 Kelish sanasi — rejalashtirilgan kelish sanasini ko'rsatish\n"
              "🔄 Yangi reys — yangi reysni boshlash\n❌ Joriy reysni tugatish — kuzatishni to'xtatish\n\n"
              "Dispetcherga savol — shunchaki shu chatga yozing.",
    },

    # ---------- водитель: сообщения от системы ----------
    "morning_request": {
        "ru": "🌅 Доброе утро!\n\nПожалуйста, отправьте ваше текущее местоположение для обновления статуса перевозки.",
        "en": "🌅 Good morning!\n\nPlease send your current location to update the trip status.",
        "uz": "🌅 Xayrli tong!\n\nIltimos, reys holatini yangilash uchun joriy joylashuvingizni yuboring.",
    },
    "lastcall_km": {
        "ru": "🏁 Внимание!\n\nДо терминала осталось менее {km} км.\n\nПожалуйста, укажите планируемую дату прибытия:",
        "en": "🏁 Attention!\n\nLess than {km} km left to the terminal.\n\nPlease set the planned arrival date:",
        "uz": "🏁 Diqqat!\n\nTerminalgacha {km} km dan kam qoldi.\n\nIltimos, rejalashtirilgan kelish sanasini ko'rsating:",
    },
    "lastcall_days": {
        "ru": "🏁 Внимание!\n\nГруз в пути уже {days} дн.\n\nПожалуйста, укажите планируемую дату прибытия:",
        "en": "🏁 Attention!\n\nThe cargo has been on the road for {days} days.\n\nPlease set the planned arrival date:",
        "uz": "🏁 Diqqat!\n\nYuk {days} kundan beri yo'lda.\n\nIltimos, rejalashtirilgan kelish sanasini ko'rsating:",
    },
    "dispatcher_asks_location": {
        "ru": "📍 Диспетчер просит отправить текущее местоположение.\nНажмите кнопку «{btn}» внизу.",
        "en": "📍 The dispatcher asks you to send your current location.\nPress «{btn}» below.",
        "uz": "📍 Dispetcher joriy joylashuvingizni yuborishni so'rayapti.\nPastdagi «{btn}» tugmasini bosing.",
    },
    "done_by_stage": {
        "ru": "✅ <b>Перевозка завершена!</b>\n\nГруз прибыл на терминал. Отслеживание остановлено.\n\n"
              "Спасибо за работу! Для новой перевозки нажмите /start",
        "en": "✅ <b>The trip is finished!</b>\n\nThe cargo has arrived at the terminal. Tracking has stopped.\n\n"
              "Thank you! For a new trip press /start",
        "uz": "✅ <b>Reys tugadi!</b>\n\nYuk terminalga yetib keldi. Kuzatish to'xtatildi.\n\n"
              "Rahmat! Yangi reys uchun /start bosing",
    },
    "done_by_dispatcher": {
        "ru": "✅ Перевозка завершена диспетчером. Отслеживание остановлено.\nДля новой перевозки нажмите /start",
        "en": "✅ The dispatcher has finished the trip. Tracking has stopped.\nFor a new trip press /start",
        "uz": "✅ Dispetcher reysni tugatdi. Kuzatish to'xtatildi.\nYangi reys uchun /start bosing",
    },
    "deal_matched": {
        "ru": "🎉 <b>Заказ найден!</b>\n\n📋 {title}\n🏭 Терминал: {terminal}\n\n"
              "Теперь ваше местоположение передаётся брокеру.",
        "en": "🎉 <b>Order found!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\n"
              "Your location is now shared with the broker.",
        "uz": "🎉 <b>Buyurtma topildi!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\n"
              "Endi joylashuvingiz brokerga yuboriladi.",
    },
    "bound_by_dispatcher": {
        "ru": "✅ <b>Перевозка привязана к заказу</b>\n\n📋 {title}\n🏭 Терминал: {terminal}\n\n"
              "Теперь ваше местоположение передаётся брокеру.",
        "en": "✅ <b>Your trip is linked to the order</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\n"
              "Your location is now shared with the broker.",
        "uz": "✅ <b>Reysingiz buyurtmaga bog'landi</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\n"
              "Endi joylashuvingiz brokerga yuboriladi.",
    },
    "new_trip_offer": {
        "ru": "🚛 <b>Обнаружена новая перевозка!</b>\n\n📋 {title}\n🏭 Терминал: {terminal}\n\nНачать отслеживание?",
        "en": "🚛 <b>A new trip has been found!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\nStart tracking?",
        "uz": "🚛 <b>Yangi reys topildi!</b>\n\n📋 {title}\n🏭 Terminal: {terminal}\n\nKuzatishni boshlaysizmi?",
    },

    # ---------- клиент и брокер ----------
    "invite_invalid": {
        "ru": "Ссылка недействительна или уже использована. Попросите новую у диспетчера.",
        "en": "The link is invalid or has already been used. Ask the dispatcher for a new one.",
        "uz": "Havola yaroqsiz yoki allaqachon ishlatilgan. Dispetcherdan yangisini so'rang.",
    },
    "joined_manager": {
        "ru": "✅ Вы подключены как менеджер. Панель управления — /admin",
        "en": "✅ You are connected as a manager. Admin panel — /admin",
        "uz": "✅ Siz menejer sifatida ulandingiz. Boshqaruv paneli — /admin",
    },
    "joined_broker": {
        "ru": "✅ Вы подключены как отправитель / брокер.\n\n«{new}» — создать рейс и получить ссылку для водителя.\n"
              "«{my}» — где сейчас машины и их маршрут.",
        "en": "✅ You are connected as a shipper / broker.\n\n«{new}» — create a trip and get a link for the driver.\n"
              "«{my}» — where the trucks are now and their route.",
        "uz": "✅ Siz jo'natuvchi / broker sifatida ulandingiz.\n\n«{new}» — reys yaratish va haydovchi uchun havola olish.\n"
              "«{my}» — mashinalar hozir qayerda va ularning yo'nalishi.",
    },
    "greet": {
        "ru": "👋 Здравствуйте{who}!\nРейсов: {n}. «{my}» — список.",
        "en": "👋 Hello{who}!\nTrips: {n}. «{my}» — the list.",
        "uz": "👋 Assalomu alaykum{who}!\nReyslar: {n}. «{my}» — ro'yxat.",
    },
    "pending_wait": {
        "ru": "⏳ Ваша заявка на рассмотрении у диспетчера. Мы сообщим, когда доступ откроется.",
        "en": "⏳ Your request is being reviewed by the dispatcher. We will let you know when access is granted.",
        "uz": "⏳ So'rovingiz dispetcher tomonidan ko'rib chiqilmoqda. Ruxsat berilganda xabar beramiz.",
    },
    "client_phone_ask": {
        "ru": "Чтобы показать ваши грузы, поделитесь номером телефона — найдём вас в базе по номеру, "
              "который вы оставляли брокеру.",
        "en": "To show your shipments, please share your phone number — we will find you by the number "
              "you gave to the broker.",
        "uz": "Yuklaringizni ko'rsatish uchun telefon raqamingizni yuboring — brokerga qoldirgan raqamingiz "
              "bo'yicha sizni topamiz.",
    },
    "broker_phone_ask": {"ru": "Поделитесь номером телефона для связи.",
                         "en": "Please share your phone number for contact.",
                         "uz": "Aloqa uchun telefon raqamingizni yuboring."},
    "btn_share_phone": {"ru": "📱 Поделиться номером", "en": "📱 Share phone number", "uz": "📱 Raqamni yuborish"},
    "need_own_phone": {
        "ru": "Нажмите кнопку «{btn}» — нужен ваш собственный номер.",
        "en": "Press «{btn}» — we need your own number.",
        "uz": "«{btn}» tugmasini bosing — o'zingizning raqamingiz kerak.",
    },
    "client_found": {
        "ru": "✅ Нашли вас: <b>{name}</b>.\nРейсов сейчас: {n}. Новые рейсы по вашим заказам появятся автоматически.",
        "en": "✅ We found you: <b>{name}</b>.\nTrips now: {n}. New trips for your orders will appear automatically.",
        "uz": "✅ Sizni topdik: <b>{name}</b>.\nHozirgi reyslar: {n}. Buyurtmalaringiz bo'yicha yangi reyslar "
              "avtomatik paydo bo'ladi.",
    },
    "client_inn_ask": {
        "ru": "Не нашли этот номер в нашей базе. Введите ИНН вашей компании (10 или 12 цифр).",
        "en": "We could not find this number. Enter your company's Russian tax ID (INN, 10 or 12 digits).",
        "uz": "Bu raqam bazamizda topilmadi. Kompaniyangizning Rossiya INN raqamini kiriting (10 yoki 12 ta raqam).",
    },
    "inn_bad": {
        "ru": "ИНН — 10 или 12 цифр. Попробуйте ещё раз или нажмите «{btn}».",
        "en": "The INN has 10 or 12 digits. Try again or press «{btn}».",
        "uz": "INN — 10 yoki 12 ta raqam. Qaytadan urinib ko'ring yoki «{btn}» tugmasini bosing.",
    },
    "request_sent": {
        "ru": "⏳ Заявка отправлена диспетчеру. Мы сообщим, когда доступ откроется.",
        "en": "⏳ Your request has been sent to the dispatcher. We will let you know when access is granted.",
        "uz": "⏳ So'rov dispetcherga yuborildi. Ruxsat berilganda xabar beramiz.",
    },
    "broker_company_ask": {
        "ru": "Напишите название вашей компании и страну (например: «Sugd Logistics, Таджикистан»).",
        "en": "Write your company name and country (for example: «Sugd Logistics, Tajikistan»).",
        "uz": "Kompaniyangiz nomi va mamlakatni yozing (masalan: «Sugd Logistics, Tojikiston»).",
    },
    "company_text_needed": {"ru": "Напишите название компании текстом.", "en": "Please write the company name as text.",
                            "uz": "Kompaniya nomini matn bilan yozing."},
    "btn_my_trips": {"ru": "📦 Мои рейсы", "en": "📦 My trips", "uz": "📦 Mening reyslarim"},
    "btn_create_trip": {"ru": "➕ Новый рейс", "en": "➕ New trip", "uz": "➕ Yangi reys yaratish"},
    "btn_write_dispatcher": {"ru": "✉️ Написать диспетчеру", "en": "✉️ Message the dispatcher",
                             "uz": "✉️ Dispetcherga yozish"},
    "no_trips": {
        "ru": "Рейсов пока нет. Когда по вашему заказу поедет машина, она появится здесь.",
        "en": "No trips yet. When a truck sets off with your order, it will appear here.",
        "uz": "Hozircha reyslar yo'q. Buyurtmangiz bilan mashina yo'lga chiqqanda, u shu yerda paydo bo'ladi.",
    },
    "trips_header": {
        "ru": "📦 <b>Рейсы</b> ({n}): 🟢 в пути, ⚪ завершён за последние 30 дней",
        "en": "📦 <b>Trips</b> ({n}): 🟢 on the way, ⚪ finished in the last 30 days",
        "uz": "📦 <b>Reyslar</b> ({n}): 🟢 yo'lda, ⚪ oxirgi 30 kunda tugagan",
    },
    "no_points_short": {"ru": "нет точек", "en": "no points", "uz": "nuqtalar yo'q"},
    "st_active": {"ru": "🟢 в пути", "en": "🟢 on the way", "uz": "🟢 yo'lda"},
    "st_done": {"ru": "⚪ завершён", "en": "⚪ finished", "uz": "⚪ tugagan"},
    "st_cancelled": {"ru": "отменён", "en": "cancelled", "uz": "bekor qilingan"},
    "card_shipment": {"ru": "📦 Отгрузка: {d}", "en": "📦 Shipped: {d}", "uz": "📦 Jo'natilgan: {d}"},
    "card_planned": {"ru": "📅 План прибытия: {d}", "en": "📅 Planned arrival: {d}", "uz": "📅 Rejadagi kelish: {d}"},
    "card_no_driver": {"ru": "👤 Водитель ещё не подключился", "en": "👤 The driver has not connected yet",
                       "uz": "👤 Haydovchi hali ulanmagan"},
    "card_now": {"ru": "📍 <b>Сейчас:</b> {addr}\n🕐 {time} ({ago})", "en": "📍 <b>Now:</b> {addr}\n🕐 {time} ({ago})",
                 "uz": "📍 <b>Hozir:</b> {addr}\n🕐 {time} ({ago})"},
    "card_dist": {"ru": "\n📏 До терминала: {km} км", "en": "\n📏 To the terminal: {km} km",
                  "uz": "\n📏 Terminalgacha: {km} km"},
    "card_no_location": {"ru": "📍 Местоположение ещё не передавалось", "en": "📍 No location has been sent yet",
                         "uz": "📍 Joylashuv hali yuborilmagan"},
    "card_at_terminal": {"ru": "🏁 У терминала с {t}", "en": "🏁 At the terminal since {t}",
                         "uz": "🏁 {t} dan beri terminal yonida"},
    "btn_where": {"ru": "📍 Где сейчас", "en": "📍 Where now", "uz": "📍 Hozir qayerda"},
    "btn_history": {"ru": "📜 История", "en": "📜 History", "uz": "📜 Tarix"},
    "btn_map": {"ru": "🗺 Маршрут на карте", "en": "🗺 Route on the map", "uz": "🗺 Xaritadagi yo'nalish"},
    "btn_refresh": {"ru": "🔄 Обновить", "en": "🔄 Refresh", "uz": "🔄 Yangilash"},
    "btn_all_trips": {"ru": "◀️ Все рейсы", "en": "◀️ All trips", "uz": "◀️ Barcha reyslar"},
    "btn_open_trip": {"ru": "🚛 Открыть рейс", "en": "🚛 Open trip", "uz": "🚛 Reysni ochish"},
    "no_access_trip": {"ru": "Нет доступа к этому рейсу", "en": "No access to this trip",
                       "uz": "Bu reysga ruxsat yo'q"},
    "no_points": {"ru": "Точек ещё нет", "en": "No points yet", "uz": "Hozircha nuqtalar yo'q"},
    "point_ago": {"ru": "Точка {ago}", "en": "Point {ago}", "uz": "Nuqta {ago}"},
    "history_header": {
        "ru": "📜 <b>История {truck}</b> — точек всего {n}, последние {k}:\n",
        "en": "📜 <b>History {truck}</b> — {n} points in total, last {k}:\n",
        "uz": "📜 <b>{truck} tarixi</b> — jami {n} ta nuqta, oxirgi {k} tasi:\n",
    },
    "history_dist": {"ru": " · {km} км до терминала", "en": " · {km} km to the terminal",
                     "uz": " · terminalgacha {km} km"},
    "new_trip_truck_ask": {
        "ru": "Введите номер тягача (или контейнера), без пробелов:",
        "en": "Enter the truck (or container) number, without spaces:",
        "uz": "Tyagach (yoki konteyner) raqamini probelsiz kiriting:",
    },
    "new_trip_inn_ask": {
        "ru": "ИНН получателя в России (10 или 12 цифр) — или «{btn}»:",
        "en": "Russian tax ID (INN) of the consignee (10 or 12 digits) — or «{btn}»:",
        "uz": "Rossiyadagi yuk qabul qiluvchining INN raqami (10 yoki 12 ta raqam) — yoki «{btn}»:",
    },
    "inn_or_skip": {"ru": "ИНН — 10 или 12 цифр, или нажмите «{btn}».",
                    "en": "The INN has 10 or 12 digits, or press «{btn}».",
                    "uz": "INN — 10 yoki 12 ta raqam yoki «{btn}» tugmasini bosing."},
    "trip_created": {"ru": "✅ <b>Рейс {truck} создан</b>", "en": "✅ <b>Trip {truck} created</b>",
                     "uz": "✅ <b>{truck} reysi yaratildi</b>"},
    "tc_deal_found": {"ru": "📋 Найден заказ: {title}\n🏭 {terminal}", "en": "📋 Order found: {title}\n🏭 {terminal}",
                      "uz": "📋 Buyurtma topildi: {title}\n🏭 {terminal}"},
    "tc_deal_not_found": {
        "ru": "Заказ с этим номером пока не найден — диспетчер привяжет его.",
        "en": "No order with this number yet — the dispatcher will link it.",
        "uz": "Bu raqamli buyurtma hali topilmadi — dispetcher uni bog'laydi.",
    },
    "tc_driver_link": {
        "ru": "\n👉 <b>Перешлите водителю ссылку:</b>\n{link}\n\nВодитель откроет её, даст согласие — "
              "и сразу окажется в этом рейсе, номер вводить не нужно.",
        "en": "\n👉 <b>Forward this link to the driver:</b>\n{link}\n\nThe driver opens it, gives consent "
              "and is connected to this trip right away — no need to enter the number.",
        "uz": "\n👉 <b>Ushbu havolani haydovchiga yuboring:</b>\n{link}\n\nHaydovchi uni ochadi, rozilik beradi "
              "va darhol shu reysga ulanadi — raqam kiritish shart emas.",
    },
    "write_dispatcher_ask": {"ru": "Напишите сообщение — передам диспетчеру.",
                             "en": "Write your message — I will pass it to the dispatcher.",
                             "uz": "Xabaringizni yozing — dispetcherga yetkazaman."},
    "access_opened": {"ru": "✅ Доступ открыт. «{my}» — где сейчас машины.",
                      "en": "✅ Access granted. «{my}» — where the trucks are now.",
                      "uz": "✅ Ruxsat berildi. «{my}» — mashinalar hozir qayerda."},
    "access_denied": {"ru": "К сожалению, в доступе отказано. Свяжитесь с диспетчером.",
                      "en": "Unfortunately, access was denied. Please contact the dispatcher.",
                      "uz": "Afsuski, ruxsat berilmadi. Dispetcher bilan bog'laning."},
    "trip_opened_to_you": {"ru": "🚛 Вам открыт рейс {truck}.", "en": "🚛 Trip {truck} is now available to you.",
                           "uz": "🚛 Sizga {truck} reysi ochildi."},
    "admin_granted": {"ru": "⭐ Вам открыта админка — /admin", "en": "⭐ Admin panel is now available — /admin",
                      "uz": "⭐ Sizga boshqaruv paneli ochildi — /admin"},
    "admin_revoked": {"ru": "Права админа сняты.", "en": "Admin rights have been removed.",
                      "uz": "Admin huquqlari olib tashlandi."},

    # ---------- события рейса для клиента и брокера ----------
    "ev_started": {
        "ru": "🚛 <b>Груз в пути</b>: {title}\nВы можете смотреть местоположение машины и маршрут в этом боте.",
        "en": "🚛 <b>Cargo on the way</b>: {title}\nYou can follow the truck's location and route in this bot.",
        "uz": "🚛 <b>Yuk yo'lda</b>: {title}\nMashinaning joylashuvi va yo'nalishini shu botda kuzatishingiz mumkin.",
    },
    "ev_border": {
        "ru": "🛂 <b>Машина пересекла границу</b>: {a} → {b}\n{title}\n📍 {addr}",
        "en": "🛂 <b>The truck crossed the border</b>: {a} → {b}\n{title}\n📍 {addr}",
        "uz": "🛂 <b>Mashina chegarani kesib o'tdi</b>: {a} → {b}\n{title}\n📍 {addr}",
    },
    "ev_border_ru": {
        "ru": "🛂 <b>Машина въехала в Россию</b>: {a} → {b}\n{title}\n📍 {addr}",
        "en": "🛂 <b>The truck has entered Russia</b>: {a} → {b}\n{title}\n📍 {addr}",
        "uz": "🛂 <b>Mashina Rossiyaga kirdi</b>: {a} → {b}\n{title}\n📍 {addr}",
    },
    "ev_arrived": {
        "ru": "🏁 <b>Машина у терминала</b>: {title}\n📍 {addr}",
        "en": "🏁 <b>The truck is at the terminal</b>: {title}\n📍 {addr}",
        "uz": "🏁 <b>Mashina terminal yonida</b>: {title}\n📍 {addr}",
    },
    "ev_soon_km": {
        "ru": "⏳ <b>Скоро прибытие</b>: {title} — до терминала менее {km} км",
        "en": "⏳ <b>Arriving soon</b>: {title} — less than {km} km to the terminal",
        "uz": "⏳ <b>Tez orada yetib keladi</b>: {title} — terminalgacha {km} km dan kam",
    },
    "ev_soon_days": {
        "ru": "⏳ <b>Скоро прибытие</b>: {title} — груз в пути {days} дн.",
        "en": "⏳ <b>Arriving soon</b>: {title} — on the road for {days} days",
        "uz": "⏳ <b>Tez orada yetib keladi</b>: {title} — yuk {days} kundan beri yo'lda",
    },
    "ev_done": {"ru": "✅ <b>Перевозка завершена</b>: {title}", "en": "✅ <b>Trip finished</b>: {title}",
                "uz": "✅ <b>Reys tugadi</b>: {title}"},

    # ---------- команды бота ----------
    "cmd_start": {"ru": "🚛 Начать / Новая перевозка", "en": "🚛 Start / New trip", "uz": "🚛 Boshlash / Yangi reys"},
    "cmd_language": {"ru": "🌐 Язык", "en": "🌐 Language", "uz": "🌐 Til"},
    "cmd_help": {"ru": "❓ Справка", "en": "❓ Help", "uz": "❓ Yordam"},
}

COUNTRIES = {
    "ru": {"ru": "Россия", "kz": "Казахстан", "uz": "Узбекистан", "tj": "Таджикистан", "kg": "Кыргызстан",
           "tm": "Туркменистан", "ir": "Иран", "az": "Азербайджан", "ge": "Грузия", "am": "Армения",
           "by": "Беларусь", "cn": "Китай", "tr": "Турция", "af": "Афганистан", "mn": "Монголия"},
    "en": {"ru": "Russia", "kz": "Kazakhstan", "uz": "Uzbekistan", "tj": "Tajikistan", "kg": "Kyrgyzstan",
           "tm": "Turkmenistan", "ir": "Iran", "az": "Azerbaijan", "ge": "Georgia", "am": "Armenia",
           "by": "Belarus", "cn": "China", "tr": "Turkey", "af": "Afghanistan", "mn": "Mongolia"},
    "uz": {"ru": "Rossiya", "kz": "Qozog'iston", "uz": "O'zbekiston", "tj": "Tojikiston", "kg": "Qirg'iziston",
           "tm": "Turkmaniston", "ir": "Eron", "az": "Ozarbayjon", "ge": "Gruziya", "am": "Armaniston",
           "by": "Belarus", "cn": "Xitoy", "tr": "Turkiya", "af": "Afg'oniston", "mn": "Mo'g'uliston"},
}


def norm(lang: Optional[str]) -> str:
    return lang if lang in LANGS else DEFAULT


def t(lang: Optional[str], key: str, **kw) -> str:
    entry = T[key]
    text = entry.get(norm(lang)) or entry[DEFAULT]
    return text.format(**kw) if kw else text


def V(key: str) -> Set[str]:
    """Все языковые варианты текста кнопки — для фильтров F.text.in_(...)."""
    return set(T[key].values())


def guess(language_code: Optional[str]) -> str:
    code = (language_code or "").lower()[:2]
    if code == "uz":
        return "uz"
    if code in ("ru", "uk", "be", "kk", "ky", "tg", ""):
        return "ru"
    return "en"


def country(lang: str, code: Optional[str]) -> str:
    return COUNTRIES[norm(lang)].get((code or "").lower(), (code or "?").upper())


def duration(lang: str, minutes: Optional[int]) -> str:
    if minutes is None:
        return ""
    h, m = divmod(int(minutes), 60)
    return t(lang, "dur_hm", h=h, m=m) if h else t(lang, "dur_m", m=m)


def ago(lang: str, dt) -> str:
    from datetime import datetime
    if not dt:
        return "—"
    sec = int((datetime.utcnow() - dt).total_seconds())
    if sec < 60:
        return t(lang, "ago_now")
    if sec < 3600:
        return t(lang, "ago_min", n=sec // 60)
    if sec < 86400:
        return t(lang, "ago_h", n=sec // 3600)
    return t(lang, "ago_d", n=sec // 86400)


_TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
     "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"],
))


def translit(text: str) -> str:
    out = []
    for ch in text or "":
        low = ch.lower()
        if low in _TRANSLIT:
            lat = _TRANSLIT[low]
            out.append(lat.capitalize() if ch.isupper() else lat)
        else:
            out.append(ch)
    return "".join(out)


def terminal_name(lang: str, terminal_code) -> str:
    """Название терминала на языке пользователя."""
    from src.config import TERMINALS, terminal_name as ru_name
    if norm(lang) == "ru":
        return ru_name(terminal_code)
    if not terminal_code:
        return "—"
    tinfo = TERMINALS.get(str(terminal_code), {})
    city = translit(tinfo.get("code") or str(terminal_code))
    return f"{city} — {tinfo['name_en']}" if tinfo.get("name_en") else city


def terminal_short(lang: str, terminal_code) -> str:
    return terminal_name(lang, terminal_code).split(" — ")[0]


def terminal_address(lang: str, terminal_code) -> str:
    from src.config import TERMINALS
    tinfo = TERMINALS.get(str(terminal_code or ""), {})
    if norm(lang) == "ru":
        return tinfo.get("address_ru", "")
    return tinfo.get("address_en") or tinfo.get("address_ru", "")


# ==================== ХРАНЕНИЕ ЯЗЫКА ====================

_cache: Dict[int, str] = {}


async def stored_lang(telegram_id: int) -> Optional[str]:
    """Язык, который пользователь выбрал сам (None — ещё не выбирал)."""
    if telegram_id in _cache:
        return _cache[telegram_id]
    from sqlalchemy import select
    from src.db.database import get_session
    from src.db.models import UserPref
    async with get_session() as session:
        result = await session.execute(select(UserPref.lang).where(UserPref.telegram_id == telegram_id))
        lang = result.scalar_one_or_none()
    if lang:
        _cache[telegram_id] = lang
    return lang


async def get_lang(telegram_id: int, language_code: Optional[str] = None) -> str:
    return norm(await stored_lang(telegram_id) or guess(language_code))


async def set_lang(telegram_id: int, lang: str):
    from sqlalchemy import select
    from src.db.database import get_session
    from src.db.models import UserPref
    lang = norm(lang)
    async with get_session() as session:
        result = await session.execute(select(UserPref).where(UserPref.telegram_id == telegram_id))
        row = result.scalar_one_or_none()
        if row:
            row.lang = lang
        else:
            session.add(UserPref(telegram_id=telegram_id, lang=lang))
    _cache[telegram_id] = lang
