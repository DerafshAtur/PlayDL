START_TEXT = (
    "سلام 👋\n\n"
    "لینک برنامه در Google Play را بفرست تا فایل APK آماده شود و همین‌جا برات ارسال کنم."
)
SEND_LINK_TEXT = "لینک Google Play برنامه را بفرست:"
BAD_LINK_TEXT = "این لینک معتبر نیست. لطفاً لینک برنامه از Google Play بفرست."
BUSY_TEXT = "چند دانلود در صف اجراست. چند لحظه دیگر دوباره تلاش کن."
CANCELLED_TEXT = "لغو شد. هر وقت آماده بودی لینک جدید بفرست."

DOWNLOAD_TITLE = "Downloading APK File..."
CONVERTING_TEXT = "فایل دانلود شد. در حال آماده‌سازی APK قابل نصب..."
UPLOAD_TITLE = "Uploading APK File to Telegram..."

DONE_TEXT = "آماده شد ✅\n{package}"
FAILED_TEXT = "عملیات ناموفق بود:\n{error}"
UNEXPECTED_ERROR_TEXT = "خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کن."

DELIVERY_PROMPT_TEXT = "فایل دانلود شده و آماده است، به چه صورت میخوای دریافتش کنی؟"
NIXFILE_PREPARING_TEXT = "در حال آماده‌سازی آپلود به نیکس‌فایل..."
NIXFILE_UPLOAD_TITLE = "Uploading APK to NixFile..."
LINK_READY_TEXT = "لینک داخلی آماده شد ✅\n{package}"
NIXFILE_DISABLED_TEXT = "آپلود به نیکس‌فایل پیکربندی نشده است."
JOB_NOT_FOUND_TEXT = "این فایل دیگر در دسترس نیست. لطفاً دوباره لینک بفرست."
NIXFILE_QUOTA_TEXT = (
    "سقف روزانه آپلود به نیکس‌فایل ({limit} فایل) به پایان رسیده است.\n"
    "فردا دوباره تلاش کن یا از گزینه تلگرام استفاده کن."
)
NIXFILE_TOO_BIG_TEXT = (
    "حجم فایل ({size_mb:.1f} MB) از سقف نیکس‌فایل ({limit_mb} MB) بیشتر است.\n"
    "از گزینه تلگرام استفاده کن."
)

RUBIKA_DISABLED_TEXT = (
    "ارسال به روبیکا فعال نیست.\n"
    "ادمین باید با اجرای `python session_rubika.py` اکانت روبیکا را وصل کند."
)
RUBIKA_PROMPT_USERNAME_TEXT = (
    "نام کاربری روبیکای خود را بفرست (با یا بدون @).\n"
    "مثلاً: @yourname"
)
RUBIKA_USERNAME_INVALID_TEXT = "نام کاربری معتبر نیست. دوباره بفرست."
RUBIKA_USER_NOT_FOUND_TEXT = "کاربر روبیکا با این نام پیدا نشد. مطمئنی نام کاربری درسته؟"
RUBIKA_UPLOADING_TEXT = "در حال ارسال فایل به روبیکا برای @{username} ..."
RUBIKA_DELIVERED_TEXT = (
    "فایل به روبیکا ارسال شد ✅\n"
    "گیرنده: {name} (@{username})\n"
    "در دایرکت روبیکا چک کن."
)
RUBIKA_TOO_BIG_TEXT = (
    "حجم فایل ({size_mb:.1f} MB) از سقف روبیکا ({limit_mb} MB) بیشتر است."
)
USER_BUSY_TEXT = (
    "یک درخواست از طرف شما در حال پردازش است. لطفاً صبر کن تا تموم بشه."
)

FILE2LINK_PROMPT_TEXT = (
    "فایل مورد نظر را ارسال کن.\n"
    "اگر بزرگ‌تر از {limit_mb} مگابایت باشد، به‌صورت rar فشرده و در صورت لزوم به چند بخش تقسیم می‌شود."
)
FILE2LINK_NO_FILE_TEXT = "لطفاً یک فایل (Document) ارسال کن."
FILE2LINK_DOWNLOADING_TEXT = "در حال دریافت فایل از تلگرام..."
FILE2LINK_PACKAGING_TEXT = "در حال فشرده‌سازی/تقسیم فایل با rar..."
FILE2LINK_UPLOADING_TEXT = "در حال آپلود به نیکس‌فایل ({index}/{total})..."
FILE2LINK_READY_SINGLE_TEXT = "لینک آماده شد ✅\n{name}"
FILE2LINK_READY_MULTI_TEXT = "لینک‌ها آماده شدند ✅\n{name}\n{count} بخش"

SEARCH_PROMPT_TEXT = "نام برنامه را برای جستجو در گوگل پلی بفرست:"
SEARCH_EMPTY_TEXT = "چیزی پیدا نشد. عبارت دیگری امتحان کن."
SEARCH_FAILED_TEXT = "جستجو ناموفق بود:\n{error}"
SEARCH_RESULTS_TEXT = "نتایج جستجو برای «{query}»:\nیکی را انتخاب کن تا دانلود شود."
SEARCH_PICKED_TEXT = "انتخاب شد:\n{package}"
