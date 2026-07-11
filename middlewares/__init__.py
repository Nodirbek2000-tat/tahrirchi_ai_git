from loader import dp

from .private import PrivateOnlyMiddleware
from .db import DbSessionMiddleware
from .subscription import SubscriptionMiddleware
from .throttling import ThrottlingMiddleware

if __name__ == "middlewares":
    dp.middleware.setup(PrivateOnlyMiddleware())  # birinchi: guruh xabarlarini to'sadi
    dp.middleware.setup(DbSessionMiddleware())
    dp.middleware.setup(SubscriptionMiddleware())
    dp.middleware.setup(ThrottlingMiddleware())
