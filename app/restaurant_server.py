from mcp.server.fastmcp import FastMCP
from typing import Literal, Any, List, Dict, Optional
import httpx
import textwrap
import uuid
from datetime import datetime, timedelta
import json
import sqlite3 # Added for SQLite

# Initialize FastMCP server
mcp = FastMCP("RestaurantChatbot")

# Constants
USER_AGENT = "restaurant-chatbot/1.0"
DB_NAME = "data/restaurant.db" # Updated path

def create_db_connection():
    """Create a database connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

# --- Helper Functions ---
def _is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def _format_menu_item_from_row(item_row: sqlite3.Row) -> str:
    """Format a menu item from a database row into a readable string."""
    return f"""
ID: {item_row['id']}
Name: {item_row['name']}
Category: {item_row['category']}
Price: ${item_row['price']:.2f}
Description: {item_row['description']}
"""

def _format_order_from_row(order_row: sqlite3.Row, items_rows: List[sqlite3.Row]) -> str:
    """Format an order from database rows into a readable string."""
    items_details = "\n".join(
        [f"- {ir['name']} (ID: {ir['menu_item_id']}) (x{ir['quantity']}): ${ir['price_at_order']*ir['quantity']:.2f}" for ir in items_rows]
    )
    return f"""
Order ID: {order_row['id']}
Customer: {order_row['customer_name']}
Items:
{items_details}
Total: ${order_row['total']:.2f}
Status: {order_row['status']}
Placed: {order_row['created_at']}
Last Updated: {order_row['updated_at']}
"""

# --- MCP Tools ---
@mcp.tool()
async def browse_menu(category: Optional[str] = None) -> str:
    """Provides information about the restaurant's menu.
    - If 'category' is NOT provided: Returns a list of all available food categories (e.g., "Main", "Beverage", "Dessert"). The user should then be asked which category they want to explore.
    - If 'category' IS provided: Returns a formatted list of all menu items within that specific category, including their ID, name, price, and description. These details, especially the 'item_id', are crucial for ordering.

    Args:
        category: Optional. The specific food category to display items from (e.g., "Main", "Salad").
    """
    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to browse menu."
    
    try:
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT * FROM menu WHERE lower(category) = lower(?) ORDER BY name", (category.strip(),))
            items_rows = cursor.fetchall()
            if not items_rows:
                # Get all available categories to suggest to the user
                cursor.execute("SELECT DISTINCT category FROM menu ORDER BY category")
                all_categories = [row['category'] for row in cursor.fetchall()]
                cat_string = ", ".join(all_categories) if all_categories else "No categories available"
                return f"No items found for category '{category}'. Perhaps try one of these: {cat_string}."
            return f"Items in category '{category}':\n" + "\n---\n".join([_format_menu_item_from_row(item) for item in items_rows])
        else:
            # List all categories
            cursor.execute("SELECT DISTINCT category FROM menu ORDER BY category")
            all_categories = [row['category'] for row in cursor.fetchall()]
            if not all_categories:
                return "The menu is currently empty."
            return "Here are our menu categories: \n- " + "\n- ".join(all_categories) + "\nWhich category would you like to see?"

    except sqlite3.Error as e:
        return f"Database error while browsing menu: {e}"
    finally:
        if conn:
            conn.close()

@mcp.tool()
async def place_order(customer_name: str, items: List[Dict[str, Any]]) -> str:
    """Place a new order with selected items and quantities.
    IMPORTANT: Each item in the 'items' list MUST use the exact 'item_id' (e.g., "1", "5", "12") obtained from the 'browse_menu' tool. Do not use item names as IDs.

    Args:
        customer_name: Name of the customer.
        items: List of {"item_id": str, "quantity": int}. 'item_id' must be a valid ID from the menu.
    """
    if not customer_name or not isinstance(customer_name, str) or not customer_name.strip():
        return "Error: Customer name must be a non-empty string."
    if not items or not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return "Error: Items must be a list of dictionaries, each with 'item_id' and 'quantity'."

    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to place order."

    order_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    order_total = 0.0
    processed_order_items = [] # To hold validated items with details for DB insertion

    try:
        cursor = conn.cursor()
        for item_data in items:
            item_id = item_data.get("item_id")
            quantity = item_data.get("quantity")

            if not item_id or not isinstance(item_id, str):
                return f"Error: Invalid item_id provided: {item_id}. It must be a string."
            if not isinstance(quantity, int) or quantity < 1:
                return f"Error: Invalid quantity for item ID {item_id}. Quantity must be a positive integer. Got: {quantity}"

            cursor.execute("SELECT id, name, price FROM menu WHERE id = ?", (item_id,))
            menu_item_row = cursor.fetchone()
            if not menu_item_row:
                return f"Error: Item ID {item_id} not found in menu. Please browse the menu for available items."
            
            item_price = menu_item_row['price']
            order_total += item_price * quantity
            processed_order_items.append({
                "order_id": order_id,
                "menu_item_id": item_id,
                "quantity": quantity,
                "price_at_order": item_price,
                "name": menu_item_row['name'] # For formatted output
            })
        
        if not processed_order_items:
            return "Error: No valid items provided in the order."

        # Insert into orders table
        cursor.execute("""
            INSERT INTO orders (id, customer_name, total, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, customer_name.strip(), order_total, "Pending", created_at, created_at))

        # Insert into order_items table
        cursor.executemany("""
            INSERT INTO order_items (order_id, menu_item_id, quantity, price_at_order)
            VALUES (:order_id, :menu_item_id, :quantity, :price_at_order)
        """, processed_order_items)
        
        conn.commit()

        # Fetch the newly created order for display
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        new_order_row = cursor.fetchone()
        # No need to pass processed_order_items to _format_order_from_row as it expects sqlite3.Row objects
        # We'll re-fetch them for consistency or adapt the formatter
        
        # For now, let's build a simple items list for the formatter
        display_items = [{"name": pi["name"], "menu_item_id": pi["menu_item_id"], "quantity": pi["quantity"], "price_at_order": pi["price_at_order"]} for pi in processed_order_items]


        return f"Order placed successfully!\n{_format_order_from_row(new_order_row, display_items)}"

    except sqlite3.Error as e:
        if conn: conn.rollback()
        return f"Database error while placing order: {e}"
    finally:
        if conn:
            conn.close()

@mcp.tool()
async def cancel_order(order_id: str) -> str:
    """Cancel an existing order by ID. Only 'Pending' or 'Modified' orders can be cancelled.

    Args:
        order_id: ID of the order to cancel.
    """
    if not _is_valid_uuid(order_id):
        return f"Error: Invalid order ID format: {order_id}. Please provide a valid order ID."

    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to cancel order."
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()

        if not order_row:
            return f"Error: Order ID {order_id} not found."
        
        if order_row["status"] not in ["Pending", "Modified", "Confirmed"]: # Allow cancelling confirmed orders too
            return f"Error: Cannot cancel order. Order status is '{order_row['status']}'. Only Pending, Modified, or Confirmed orders can be cancelled."
        
        updated_at = datetime.utcnow().isoformat()
        cursor.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", ("Cancelled", updated_at, order_id))
        conn.commit()

        if cursor.rowcount == 0:
            return f"Error: Failed to update order {order_id}. It might have been modified or deleted by another process."

        # Fetch updated order and its items for display
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        updated_order_row = cursor.fetchone()
        cursor.execute("""
            SELECT oi.quantity, oi.price_at_order, oi.menu_item_id, m.name
            FROM order_items oi
            JOIN menu m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ?
        """, (order_id,))
        items_rows = cursor.fetchall()
        
        return f"Order {order_id} cancelled successfully.\n{_format_order_from_row(updated_order_row, items_rows)}"
    except sqlite3.Error as e:
        if conn: conn.rollback()
        return f"Database error while cancelling order: {e}"
    finally:
        if conn:
            conn.close()

@mcp.tool()
async def modify_order(order_id: str, items: List[Dict[str, Any]]) -> str:
    """Modify an existing order by replacing its items. Only 'Pending' or 'Modified' orders can be modified.

    Args:
        order_id: ID of the order to modify.
        items: List of {"item_id": str, "quantity": int} to replace existing items.
    """
    if not _is_valid_uuid(order_id):
        return f"Error: Invalid order ID format: {order_id}. Please provide a valid order ID."
    if not items or not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return "Error: New items must be a list of dictionaries, each with 'item_id' and 'quantity'."

    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to modify order."

    try:
        cursor = conn.cursor()
        # Check current order status
        cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
        order_status_row = cursor.fetchone()
        if not order_status_row:
            return f"Error: Order ID {order_id} not found."
        if order_status_row["status"] not in ["Pending", "Modified"]:
            return f"Error: Cannot modify order. Order status is '{order_status_row['status']}'. Only Pending or Modified orders can be changed."

        new_order_total = 0.0
        processed_new_items = []

        for item_data in items:
            item_id = item_data.get("item_id")
            quantity = item_data.get("quantity")

            if not item_id or not isinstance(item_id, str):
                return f"Error: Invalid new item_id provided: {item_id}. It must be a string."
            if not isinstance(quantity, int) or quantity < 1:
                return f"Error: Invalid quantity for new item ID {item_id}. Quantity must be a positive integer."

            cursor.execute("SELECT id, name, price FROM menu WHERE id = ?", (item_id,))
            menu_item_row = cursor.fetchone()
            if not menu_item_row:
                return f"Error: New item ID {item_id} not found in menu."
            
            item_price = menu_item_row['price']
            new_order_total += item_price * quantity
            processed_new_items.append({
                "order_id": order_id,
                "menu_item_id": item_id,
                "quantity": quantity,
                "price_at_order": item_price,
                "name": menu_item_row['name']
            })
        
        if not processed_new_items:
            return "Error: No valid new items provided for modification."

        # Start transaction
        cursor.execute("BEGIN TRANSACTION") # Explicit transaction

        # Delete old items for this order
        cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))

        # Insert new items
        cursor.executemany("""
            INSERT INTO order_items (order_id, menu_item_id, quantity, price_at_order)
            VALUES (:order_id, :menu_item_id, :quantity, :price_at_order)
        """, processed_new_items)

        # Update order total and status
        updated_at = datetime.utcnow().isoformat()
        cursor.execute("""
            UPDATE orders SET total = ?, status = ?, updated_at = ?
            WHERE id = ?
        """, (new_order_total, "Modified", updated_at, order_id))
        
        conn.commit()

        # Fetch the modified order for display
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        modified_order_row = cursor.fetchone()
        # Fetch the newly inserted items for display
        display_items_mod = [{"name": pi["name"], "menu_item_id": pi["menu_item_id"], "quantity": pi["quantity"], "price_at_order": pi["price_at_order"]} for pi in processed_new_items]


        return f"Order {order_id} modified successfully!\n{_format_order_from_row(modified_order_row, display_items_mod)}"

    except sqlite3.Error as e:
        if conn: conn.rollback()
        return f"Database error while modifying order: {e}"
    finally:
        if conn:
            conn.close()

@mcp.tool()
async def view_order_history(customer_name: str) -> str:
    """View all orders placed by a specific customer.

    Args:
        customer_name: Name of the customer.
    """
    if not customer_name or not isinstance(customer_name, str) or not customer_name.strip():
        return "Error: Customer name must be a non-empty string."

    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to view order history."

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE lower(customer_name) = lower(?) ORDER BY created_at DESC", (customer_name.strip(),))
        orders_rows = cursor.fetchall()

        if not orders_rows:
            return f"No orders found for customer '{customer_name.strip()}'."

        formatted_orders = []
        for order_row in orders_rows:
            cursor.execute("""
                SELECT oi.quantity, oi.price_at_order, oi.menu_item_id, m.name
                FROM order_items oi
                JOIN menu m ON oi.menu_item_id = m.id
                WHERE oi.order_id = ?
            """, (order_row["id"],))
            items_rows = cursor.fetchall()
            formatted_orders.append(_format_order_from_row(order_row, items_rows))
        
        return "\n---\n".join(formatted_orders)
    except sqlite3.Error as e:
        return f"Database error while viewing order history: {e}"
    finally:
        if conn:
            conn.close()

@mcp.tool()
async def estimate_delivery_time(order_id: str) -> str:
    """Estimate preparation and delivery time for a specific order.

    Args:
        order_id: ID of the order.
    """
    if not _is_valid_uuid(order_id):
        return f"Error: Invalid order ID format: {order_id}. Please provide a valid order ID."

    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to estimate delivery."

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()

        if not order_row:
            return f"Error: Order ID {order_id} not found."
        
        current_status = order_row["status"]
        if current_status in ["Delivered", "Cancelled"]:
            return f"Cannot estimate delivery for order {order_id}. Its status is '{current_status}'."
        
        # Fetch order items to calculate prep time
        cursor.execute("SELECT quantity FROM order_items WHERE order_id = ?", (order_id,))
        items_rows = cursor.fetchall()
        
        if not items_rows: # Should not happen if order exists, but good to check
             return f"Error: No items found for order {order_id} to estimate delivery."

        total_items_count = sum(item_row["quantity"] for item_row in items_rows)
        
        # Simple estimation: 5 min base + 2 min per item for prep
        prep_time_minutes = 5 + (2 * total_items_count)
        # Standard delivery time
        delivery_service_time_minutes = 15 
        
        total_estimated_minutes = prep_time_minutes + delivery_service_time_minutes
        
        # If order is already being prepared or ready, adjust estimate
        try:
            order_created_at = datetime.fromisoformat(order_row["created_at"])
            time_since_creation = datetime.utcnow() - order_created_at
            
            if current_status == "Preparing":
                 # Assume prep started shortly after order or modification
                 # For simplicity, let's say half of prep_time is already passed if it was recently updated
                 order_updated_at = datetime.fromisoformat(order_row["updated_at"])
                 if (datetime.utcnow() - order_updated_at) < timedelta(minutes=prep_time_minutes / 2):
                     remaining_prep_time = prep_time_minutes / 2
                 else: # if a long time has passed, assume prep is nearly done or just finished
                     remaining_prep_time = max(5, prep_time_minutes - (datetime.utcnow() - order_updated_at).total_seconds() / 60)
                 total_estimated_minutes = remaining_prep_time + delivery_service_time_minutes

            elif current_status == "Ready": # If ready for delivery
                total_estimated_minutes = delivery_service_time_minutes
            
            elif current_status == "Confirmed": # Just confirmed, full prep + delivery
                 total_estimated_minutes = prep_time_minutes + delivery_service_time_minutes

        except ValueError: # If timestamp is malformed, fall back to default full estimate
            pass


        estimated_delivery_datetime = datetime.utcnow() + timedelta(minutes=total_estimated_minutes)
        
        return f"Estimated delivery for order {order_id} ({current_status}): Around {estimated_delivery_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')} (approx. {int(total_estimated_minutes)} minutes from now)."
    except sqlite3.Error as e:
        return f"Database error while estimating delivery time: {e}"
    finally:
        if conn:
            conn.close()

@mcp.tool()
async def update_order_status(order_id: str, new_status: Literal["Confirmed", "Preparing", "Ready", "Delivered"]) -> str:
    """Update the status of an existing order.
    Allowed transitions:
    - Pending -> Confirmed, Preparing
    - Confirmed -> Preparing
    - Modified -> Confirmed, Preparing
    - Preparing -> Ready
    - Ready -> Delivered

    Args:
        order_id: ID of the order to update.
        new_status: The new status for the order.
    """
    if not _is_valid_uuid(order_id):
        return f"Error: Invalid order ID format: {order_id}."
    
    allowed_statuses = ["Confirmed", "Preparing", "Ready", "Delivered"]
    if new_status not in allowed_statuses:
        return f"Error: Invalid new status '{new_status}'. Must be one of: {', '.join(allowed_statuses)}."

    conn = create_db_connection()
    if not conn:
        return "Error: Could not connect to the database to update order status."

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()

        if not order_row:
            return f"Error: Order ID {order_id} not found."

        current_status = order_row["status"]
        
        # Define valid transitions
        valid_transitions = {
            "Pending": ["Confirmed", "Preparing"],
            "Confirmed": ["Preparing"],
            "Modified": ["Confirmed", "Preparing"],
            "Preparing": ["Ready"],
            "Ready": ["Delivered"],
            # Cancelled and Delivered are terminal states for this tool
        }

        if new_status == current_status:
            return f"Order {order_id} is already in '{current_status}' status."

        if current_status not in valid_transitions or new_status not in valid_transitions.get(current_status, []):
            allowed_next = ", ".join(valid_transitions.get(current_status,[])) or "None (terminal status)"
            return f"Error: Cannot change order status from '{current_status}' to '{new_status}'. Allowed next statuses for '{current_status}': {allowed_next}."
            
        updated_at = datetime.utcnow().isoformat()
        cursor.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (new_status, updated_at, order_id))
        conn.commit()

        if cursor.rowcount == 0:
             return f"Error: Failed to update order {order_id} status. It might have been modified or deleted by another process."

        # Fetch updated order and its items for display
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        updated_order_row = cursor.fetchone()
        cursor.execute("""
            SELECT oi.quantity, oi.price_at_order, oi.menu_item_id, m.name
            FROM order_items oi
            JOIN menu m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ?
        """, (order_id,))
        items_rows = cursor.fetchall()

        return f"Order {order_id} status updated to '{new_status}'.\n{_format_order_from_row(updated_order_row, items_rows)}"
    except sqlite3.Error as e:
        if conn: conn.rollback()
        return f"Database error while updating order status: {e}"
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # This part is important: Ensure the database and tables are created before running the server.
    # You should run `python -m app.db_setup` once before starting the server for the first time.
    # For robustness, we can add a check here or ensure it's part of deployment.
    
    # Quick check for db existence, not a full setup.
    # Proper setup should be a separate step.
    import os
    if not os.path.exists(DB_NAME):
        print(f"Warning: Database file '{DB_NAME}' not found.")
        print("Please run 'python -m app.db_setup' to create and populate the database.") # Updated command
        # For a more robust server, you might want to exit or attempt setup here.
        # For now, we'll let it try to connect, which will likely fail if db/tables don't exist.

    mcp.run(transport="stdio")