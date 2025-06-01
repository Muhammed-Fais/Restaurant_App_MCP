import sqlite3

DB_NAME = "data/restaurant.db"

MENU_ITEMS = [
    {"id": "1", "name": "Margherita Pizza", "category": "Main", "price": 12.99, "description": "Classic pizza with tomato, mozzarella, and basil"},
    {"id": "2", "name": "Caesar Salad", "category": "Salad", "price": 8.99, "description": "Fresh romaine, croutons, and Caesar dressing"},
    {"id": "3", "name": "Spaghetti Carbonara", "category": "Main", "price": 14.99, "description": "Pasta with creamy egg sauce and pancetta"},
    {"id": "4", "name": "Tiramisu", "category": "Dessert", "price": 6.99, "description": "Coffee-flavored Italian dessert"},
    {"id": "5", "name": "Porotta Roll (Chicken)", "category": "Rolls", "price": 7.50, "description": "Flaky porotta bread rolled with spiced chicken filling"},
    {"id": "6", "name": "Karak Chai", "category": "Beverage", "price": 2.50, "description": "Strong, spiced tea with milk, a popular classic"},
    {"id": "7", "name": "Fresh Milk Tea", "category": "Beverage", "price": 2.00, "description": "Traditional tea made with fresh milk"},
    {"id": "8", "name": "Butter Chicken", "category": "Main", "price": 15.99, "description": "Creamy and tangy grilled chicken in a rich tomato sauce"},
    {"id": "9", "name": "Vegetable Biryani", "category": "Main", "price": 13.50, "description": "Aromatic basmati rice cooked with mixed vegetables and spices"},
    {"id": "10", "name": "Chicken Shawarma Plate", "category": "Main", "price": 11.99, "description": "Sliced marinated chicken served with pita and garlic sauce"},
    {"id": "11", "name": "Falafel Wrap", "category": "Rolls", "price": 8.00, "description": "Crispy falafel balls with tahini sauce and veggies in a wrap"},
    {"id": "12", "name": "Mango Lassi", "category": "Beverage", "price": 4.50, "description": "Cooling yogurt-based mango smoothie"},
    {"id": "13", "name": "Beef Burger", "category": "Main", "price": 10.50, "description": "Grilled beef patty with lettuce, tomato, and cheese"},
    {"id": "14", "name": "Fries", "category": "Side", "price": 3.50, "description": "Crispy golden french fries"},
    {"id": "15", "name": "Coke", "category": "Beverage", "price": 1.50, "description": "Classic Coca-Cola"}
]

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def create_tables(conn):
    """Create tables if they don't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL, -- Pending, Confirmed, Preparing, Ready, Delivered, Cancelled, Modified
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                menu_item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_at_order REAL NOT NULL, -- Price of the item when the order was placed
                FOREIGN KEY (order_id) REFERENCES orders (id),
                FOREIGN KEY (menu_item_id) REFERENCES menu (id)
            );
        """)
        conn.commit()
        print("Tables created successfully.")
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")

def populate_menu(conn):
    """Populate the menu table if it's empty."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM menu")
        if cursor.fetchone()[0] == 0:
            print("Menu is empty, populating...")
            cursor.executemany("""
                INSERT INTO menu (id, name, category, price, description)
                VALUES (:id, :name, :category, :price, :description)
            """, MENU_ITEMS)
            conn.commit()
            print(f"{len(MENU_ITEMS)} items inserted into menu.")
        else:
            print("Menu already populated.")
    except sqlite3.Error as e:
        print(f"Error populating menu: {e}")

if __name__ == "__main__":
    conn = create_connection()
    if conn:
        create_tables(conn)
        populate_menu(conn)
        conn.close()
        print(f"Database setup complete. Database is at {DB_NAME}") 