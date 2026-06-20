import strategy

print(strategy.__file__)

from data import get_history
from indicators import add_indicators
from strategy import trend_start

df = get_history("AOT", "SET")
df = add_indicators(df)

result = trend_start(df)

print(result)