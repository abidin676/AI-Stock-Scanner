from data import get_history
from indicators import add_indicators

from strategy_engine.stage_analysis import get_stage

symbol = "AAPL"

df = get_history(symbol, "USA")

df = add_indicators(df)

print(symbol)

print(get_stage(df))

print(df.columns)
print(df.tail())