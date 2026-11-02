"""Стартовый каталог серверов.

Источник: прайс-лист владельца (лист "Virt Shop").
Берём ТОЛЬКО «Нашу цену при -20%», пересчитанную на 1кк (1 000 000 виртов).
Формат: (код игры, название сервера, цена за 1к в рублях, остаток в кк)
"""

SEED_SERVERS: list[tuple[str, str, str, float]] = [
    # ---- Majestic RP ----
    ("majestic", "N01 New York",      "0.672", 384),
    ("majestic", "N02 Detroit",       "0.312", 217),
    ("majestic", "N03 Chicago",       "0.296", 463),
    ("majestic", "N04 San Francisco", "0.184", 291),
    ("majestic", "N05 Atlanta",       "0.224", 176),
    ("majestic", "N06 San Diego",     "0.248", 428),
    ("majestic", "N07 Los Angeles",   "0.248", 352),
    ("majestic", "N08 Miami",         "0.240", 249),
    ("majestic", "N09 Las Vegas",     "0.192", 491),
    ("majestic", "N10 Washington",    "0.184", 318),
    ("majestic", "N11 Dallas",        "0.296", 203),
    ("majestic", "N12 Boston",        "0.248", 447),
    ("majestic", "N13 Houston",       "0.432", 269),
    ("majestic", "N14 Seattle",       "0.232", 376),
    ("majestic", "N15 Phoenix",       "0.232", 158),
    ("majestic", "N16 Denver",        "0.240", 412),
    ("majestic", "N17 Portland",      "0.240", 326),
    ("majestic", "N18 Orlando",       "0.384", 184),
    ("majestic", "N19 Memphis",       "0.392", 475),
    # ---- Russia Online ----
    ("russia", "Тверской",    "0.480", 186),
    ("russia", "Кутузовский", "0.432", 273),
    ("russia", "Арбатский",   "0.392", 224),
]
