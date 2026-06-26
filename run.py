import os

while True:

    print("\n" + "=" * 50)
    print("        RIVER ALPHA V1.0")
    print("=" * 50)

    print("1. Scan Market")
    print("2. Dashboard")
    print("3. Backtest")
    print("4. Equity")
    print("5. Backtest Report")
    print("6. Update Watchlists")
    print("0. Exit")

    choice = input("\nSelect : ")

    if choice == "1":

        os.system("python scanner.py")

    elif choice == "2":

        os.system("streamlit run dashboard.py")

    elif choice == "3":

        os.system("python test/test_backtest.py")

    elif choice == "4":

        os.system("python equity.py")

    elif choice == "5":

        os.system("python backtest_report.py")

    elif choice == "6":

        os.system("python update_watchlists.py")

    elif choice == "0":

        break

    else:

        print("Invalid Menu")