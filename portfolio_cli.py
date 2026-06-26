from portfolio_manager import (
    add_position,
    show_portfolio,
    sell_position
)

while True:

    print("\n==============================")
    print(" River Alpha Portfolio")
    print("==============================")
    print("1. Show Portfolio")
    print("2. Add Position")
    print("3. Sell Position")
    print("4. Exit")
    print("==============================")

    choice = input("Select : ")

    # ==========================
    # SHOW
    # ==========================

    if choice == "1":

        show_portfolio()

    # ==========================
    # ADD
    # ==========================

    elif choice == "2":

        symbol = input("Symbol : ").upper()

        qty = int(
            input("Qty : ")
        )

        buy_price = float(
            input("Buy Price : ")
        )

        buy_date = input(
            "Buy Date (YYYY-MM-DD): "
        )

        stop = float(
            input("Stop Loss : ")
        )

        target = float(
            input("Target : ")
        )

        market = input(
            "Market (USA/SET): "
        ).upper()

        add_position(
            symbol,
            qty,
            buy_price,
            buy_date,
            stop,
            target,
            market
        )

    # ==========================
    # SELL
    # ==========================

    elif choice == "3":

        symbol = input(
            "Symbol : "
        ).upper()

        sell_position(symbol)

    # ==========================
    # EXIT
    # ==========================

    elif choice == "4":

        break

    else:

        print("Invalid Menu")
def show_portfolio():

    df = load_portfolio()

    if df.empty:

        print("\nPortfolio Empty\n")

        return

    print()

    print(df)

    print()

    print(f"Total Positions : {len(df)}")
def sell_position(symbol):

    df = load_portfolio()

    if symbol.upper() not in df["Symbol"].values:

        print("Position Not Found")

        return

    df = df[
        df["Symbol"] != symbol.upper()
    ]

    save_portfolio(df)

    print(f"Sold {symbol}")    