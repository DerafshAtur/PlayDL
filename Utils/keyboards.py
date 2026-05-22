from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 ارسال لینک گوگل پلی", callback_data="send_link")],
            [InlineKeyboardButton(text="🔍 جستجوی اپ", callback_data="search_app")],
            [InlineKeyboardButton(text="🔗 فایل به لینک", callback_data="file2link")],
        ]
    )


def search_results_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        title = item.get("title", "").strip()
        developer = item.get("developer", "").strip()
        label = title if not developer else f"{title} — {developer}"
        label = label[:60]
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"pick:{item['package']}")]
        )
    rows.append([InlineKeyboardButton(text="لغو", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="لغو", callback_data="cancel")],
        ]
    )


def delivery_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="تلگرام", callback_data=f"deliver:tg:{job_id}"),
                InlineKeyboardButton(text="لینک داخلی", callback_data=f"deliver:nx:{job_id}"),
            ],
            [
                InlineKeyboardButton(text="ارسال به روبیکا", callback_data=f"deliver:rb:{job_id}"),
            ],
        ]
    )


def link_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="دانلود فایل", url=url)],
        ]
    )


def multi_link_keyboard(urls: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if len(urls) == 1:
        rows.append([InlineKeyboardButton(text="دانلود فایل", url=urls[0])])
    else:
        for index, url in enumerate(urls, start=1):
            rows.append([InlineKeyboardButton(text=f"دانلود بخش {index}", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
