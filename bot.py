import logging
import uuid
import threading
import io
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import qrcode

from config import Config
from database import Database
from wallets import WalletManager

# Flask app for Render health checks
app = Flask(__name__)

@app.route('/')
def health_check():
    return "✅ Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
wallet_manager = WalletManager()
USER_STATES = {}

def is_admin(user_id):
    return user_id in Config.ADMIN_IDS

def generate_qr_code(data):
    """Generate QR code for a wallet address"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    # Clear any user state
    if user.id in USER_STATES:
        del USER_STATES[user.id]
    
    welcome_text = """
🤖 *Welcome to Crypto Escrow Bot!*

Hi {first_name}! I'm your secure escrow service for cryptocurrency transactions.

*Supported Currencies:*
💰 BTC • ETH • LTC • DOGE • USDT

*How It Works:*
1️⃣ You and seller agree on a trade
2️⃣ Create an escrow with the bot
3️⃣ Make payment to seller
4️⃣ Seller delivers the goods/service
5️⃣ You confirm and release funds

*Commands:*
📝 /create - Start a new escrow
📊 /list - View your escrows
ℹ️ /help - Get help
🆘 /support - Contact support
❌ /cancel - Cancel operation

*Security Features:*
🔐 All transactions are tracked
🛡️ Dispute resolution available
✅ Low 0.5% fee

Ready to get started? Click the button below!
    """.format(first_name=user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("📝 Create Escrow", callback_data="create_escrow")],
        [InlineKeyboardButton("📊 My Escrows", callback_data="my_escrows")],
        [InlineKeyboardButton("🆘 Support", callback_data="support")],
        [InlineKeyboardButton("💰 Check Balances", callback_data="balance")]
    ]
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support command - works both as command and callback"""
    query = update.callback_query
    
    support_text = """
🆘 *Support Center*

*Need Help?* We're here for you!

*Common Issues:*
1️⃣ *Escrow Creation*
   - Make sure you have the seller's username
   - Verify the amount is correct
   - Check minimum amounts

2️⃣ *Making Payment*
   - Copy the seller's address
   - Send exact amount
   - Click "I've Made Payment" after sending

3️⃣ *Releasing Funds*
   - Use /release <escrow_id>
   - Only the buyer can release funds
   - Funds are manually sent

4️⃣ *Disputes*
   - Contact support immediately
   - Provide your escrow ID
   - Explain the issue clearly

*Support Channels:*
💬 Telegram: @oxymoronic01
🕐 Response Time: ~10 minutes

*Escrow ID Format:*
Your escrow ID looks like: abc12345
Keep it safe!

*Quick Tips:*
• Always double-check wallet addresses
• Send EXACT amount shown
• Keep your Escrow ID safe
• Only release funds after receiving goods/service
    """
    
    keyboard = [
        [InlineKeyboardButton("📝 Create Escrow", callback_data="create_escrow")],
        [InlineKeyboardButton("📊 My Escrows", callback_data="my_escrows")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    if query:
        await query.answer()
        try:
            await query.edit_message_text(
                support_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await query.message.reply_text(
                support_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.message.reply_text(
            support_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def create_escrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id in USER_STATES:
        await query.edit_message_text("❌ You have an ongoing process. Use /cancel to cancel it.")
        return
    
    USER_STATES[user_id] = {"state": "awaiting_currency"}
    
    keyboard = [
        [InlineKeyboardButton("BTC", callback_data="cur_BTC"), InlineKeyboardButton("ETH", callback_data="cur_ETH")],
        [InlineKeyboardButton("LTC", callback_data="cur_LTC"), InlineKeyboardButton("DOGE", callback_data="cur_DOGE")],
        [InlineKeyboardButton("USDT", callback_data="cur_USDT")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    
    await query.edit_message_text(
        "🪙 *Step 1: Select Currency*\n\nChoose the cryptocurrency for this escrow:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    user_id = query.from_user.id
    currency = query.data.split("_")[1]
    
    if user_id not in USER_STATES:
        await query.edit_message_text("❌ Session expired. Use /create to start over.")
        return
    
    USER_STATES[user_id]["currency"] = currency
    USER_STATES[user_id]["state"] = "awaiting_seller_username"
    
    text = f"""👤 Step 2: Enter Seller's Username

Currency: {currency}

Please enter the seller's Telegram username (with @):

Example: @seller_name"""
    
    await query.edit_message_text(text)
    context.user_data["waiting_for"] = "seller_username"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in USER_STATES:
        await update.message.reply_text("Use /create to start a new escrow.")
        return
    
    state = USER_STATES[user_id]
    
    if state.get("state") == "awaiting_seller_username":
        seller = update.message.text.strip().replace("@", "")
        if len(seller) < 1:
            await update.message.reply_text("❌ Invalid username. Please enter a valid Telegram username with @:")
            return
        
        state["seller_username"] = seller
        state["state"] = "awaiting_seller_address"
        
        currency = state["currency"]
        text = f"""📤 Step 3: Enter Seller's Wallet Address

Seller: @{seller}
Currency: {currency}

Please enter the seller's {currency} wallet address:

⚠️ Double-check the address to avoid errors!"""
        
        await update.message.reply_text(text)
        context.user_data["waiting_for"] = "seller_address"
    
    elif state.get("state") == "awaiting_seller_address":
        seller_address = update.message.text.strip()
        currency = state["currency"]
        
        # Validate the address
        is_valid = wallet_manager.validate_address(currency, seller_address)
        if not is_valid:
            await update.message.reply_text(
                f"❌ Invalid {currency} address format.\n\nPlease enter a valid {currency} address:"
            )
            return
        
        state["seller_address"] = seller_address
        state["state"] = "awaiting_amount"
        
        text = f"""💰 Step 4: Enter Amount

Seller: @{state['seller_username']}
Currency: {currency}
Seller Address: {seller_address}

Enter the amount of {currency} to be held in escrow:

Minimum: {Config.MIN_AMOUNTS.get(currency, 0.0001)} {currency}"""
        
        await update.message.reply_text(text)
        context.user_data["waiting_for"] = "amount"
    
    elif state.get("state") == "awaiting_amount":
        try:
            amount = float(update.message.text.strip())
            currency = state["currency"]
            min_amount = Config.MIN_AMOUNTS.get(currency, 0.0001)
            
            if amount < min_amount:
                await update.message.reply_text(f"❌ Minimum is {min_amount} {currency}. Please enter a valid amount:")
                return
            
            state["amount"] = amount
            state["state"] = "awaiting_confirmation"
            
            fee = amount * (Config.ESCROW_FEE / 100)
            total = amount + fee
            
            escrow_id = str(uuid.uuid4())[:8]
            
            # Create escrow with seller_address
            db.create_escrow(
                escrow_id=escrow_id,
                buyer_id=user_id,
                seller_id=0,
                seller_username=state["seller_username"],
                seller_address=state["seller_address"],
                currency=currency,
                amount=amount,
                fee=fee
            )
            state["escrow_id"] = escrow_id
            
            keyboard = [
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_escrow")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            
            text = f"""✅ Step 5: Confirm Escrow Details

📋 Escrow ID: `{escrow_id}`
💱 Currency: {currency}
💰 Amount: {amount} {currency}
📊 Fee: {fee} {currency} ({Config.ESCROW_FEE}%)
💵 Total: {total} {currency}
👤 Seller: @{state['seller_username']}
📤 Seller Address: `{state['seller_address']}`

⚠️ Please review all details carefully.
Confirm to create the escrow."""
            
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a valid number:")

async def confirm_escrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in USER_STATES:
        await query.edit_message_text("❌ Session expired.")
        return
    
    state = USER_STATES[user_id]
    escrow_id = state.get("escrow_id")
    currency = state.get("currency")
    seller_address = state.get("seller_address")
    seller_username = state.get("seller_username")
    amount = state.get("amount")
    
    if not escrow_id:
        await query.edit_message_text("❌ Error.")
        return
    
    db.update_escrow_status(escrow_id, "pending")
    
    # Get all wallet addresses
    btc_address = Config.YOUR_WALLETS.get("BTC")
    eth_address = Config.YOUR_WALLETS.get("ETH")
    ltc_address = Config.YOUR_WALLETS.get("LTC")
    doge_address = Config.YOUR_WALLETS.get("DOGE")
    usdt_address = Config.YOUR_WALLETS.get("USDT")
    
    # Create payment keyboard with payment options
    keyboard = [
        [InlineKeyboardButton("💰 Pay with BTC", callback_data="pay_btc")],
        [InlineKeyboardButton("💰 Pay with ETH", callback_data="pay_eth")],
        [InlineKeyboardButton("💰 Pay with LTC", callback_data="pay_ltc")],
        [InlineKeyboardButton("💰 Pay with DOGE", callback_data="pay_doge")],
        [InlineKeyboardButton("💰 Pay with USDT", callback_data="pay_usdt")],
        [InlineKeyboardButton("📤 Show Seller Address", callback_data=f"show_seller_{escrow_id}")],
        [InlineKeyboardButton("✅ I've Made Payment", callback_data=f"payment_done_{escrow_id}")],
        [InlineKeyboardButton("📊 View Escrow", callback_data=f"view_escrow_{escrow_id}")],
        [InlineKeyboardButton("🆘 Support", callback_data="support")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    text = f"""✅ *ESCROW CREATED SUCCESSFULLY!*

📋 Escrow ID: `{escrow_id}`
💱 Currency: {currency}
💰 Amount: {amount} {currency}
👤 Seller: @{seller_username}

━━━━━━━━━━━━━━━━━━━━━━

📤 Seller's Wallet Address:
`{seller_address}`

━━━━━━━━━━━━━━━━━━━━━━

💰 Your Wallet Addresses (Buyer):

💵 BTC: `{btc_address}`
💎 ETH: `{eth_address}`
🥇 LTC: `{ltc_address}`
🐕 DOGE: `{doge_address}`
💵 USDT: `{usdt_address}`

━━━━━━━━━━━━━━━━━━━━━━

💰 Amount to Send: {amount} {currency}

⏳ NEXT STEPS:

1️⃣ Click "Pay with [Currency]" button below
2️⃣ Copy the payment address or scan QR code
3️⃣ Send {amount} {currency} to the address
4️⃣ Click "I've Made Payment" after sending
5️⃣ Seller delivers the goods/service

━━━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT NOTES:
• Send the EXACT amount shown above
• Double-check the address before sending
• Keep this Escrow ID: `{escrow_id}`
• For help, contact @oxymoronic01"""
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Clear user state
    del USER_STATES[user_id]

async def handle_payment_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment-related callback queries"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    data = query.data
    
    # Handle payment for each currency
    if data == "pay_btc":
        address = Config.YOUR_WALLETS.get("BTC")
        
        # Generate QR code
        qr_image = generate_qr_code(address)
        
        if qr_image:
            await query.message.reply_photo(
                photo=qr_image,
                caption=f"💰 *PAY WITH BTC*\n\n"
                        f"📱 Scan QR Code or copy the address below:\n\n"
                        f"`{address}`\n\n"
                        f"📱 Tap and hold the address to copy it.\n"
                        f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(
                f"💰 *PAY WITH BTC*\n\n"
                f"`{address}`\n\n"
                f"📱 Tap and hold the address to copy it.\n"
                f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        await query.answer("BTC payment address shown!")
        return
    
    elif data == "pay_eth":
        address = Config.YOUR_WALLETS.get("ETH")
        
        qr_image = generate_qr_code(address)
        
        if qr_image:
            await query.message.reply_photo(
                photo=qr_image,
                caption=f"💰 *PAY WITH ETH*\n\n"
                        f"📱 Scan QR Code or copy the address below:\n\n"
                        f"`{address}`\n\n"
                        f"📱 Tap and hold the address to copy it.\n"
                        f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(
                f"💰 *PAY WITH ETH*\n\n"
                f"`{address}`\n\n"
                f"📱 Tap and hold the address to copy it.\n"
                f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        await query.answer("ETH payment address shown!")
        return
    
    elif data == "pay_ltc":
        address = Config.YOUR_WALLETS.get("LTC")
        
        qr_image = generate_qr_code(address)
        
        if qr_image:
            await query.message.reply_photo(
                photo=qr_image,
                caption=f"💰 *PAY WITH LTC*\n\n"
                        f"📱 Scan QR Code or copy the address below:\n\n"
                        f"`{address}`\n\n"
                        f"📱 Tap and hold the address to copy it.\n"
                        f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(
                f"💰 *PAY WITH LTC*\n\n"
                f"`{address}`\n\n"
                f"📱 Tap and hold the address to copy it.\n"
                f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        await query.answer("LTC payment address shown!")
        return
    
    elif data == "pay_doge":
        address = Config.YOUR_WALLETS.get("DOGE")
        
        qr_image = generate_qr_code(address)
        
        if qr_image:
            await query.message.reply_photo(
                photo=qr_image,
                caption=f"💰 *PAY WITH DOGE*\n\n"
                        f"📱 Scan QR Code or copy the address below:\n\n"
                        f"`{address}`\n\n"
                        f"📱 Tap and hold the address to copy it.\n"
                        f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(
                f"💰 *PAY WITH DOGE*\n\n"
                f"`{address}`\n\n"
                f"📱 Tap and hold the address to copy it.\n"
                f"⚠️ Send the EXACT amount to this address.",
                parse_mode=ParseMode.MARKDOWN
            )
        await query.answer("DOGE payment address shown!")
        return
    
    elif data == "pay_usdt":
        address = Config.YOUR_WALLETS.get("USDT")
        
        qr_image = generate_qr_code(address)
        
        if qr_image:
            await query.message.reply_photo(
                photo=qr_image,
                caption=f"💰 *PAY WITH USDT*\n\n"
                        f"📱 Scan QR Code or copy the address below:\n\n"
                        f"`{address}`\n\n"
                        f"📱 Tap and hold the address to copy it.\n"
                        f"⚠️ Send the EXACT amount to this address.\n"
                        f"🌐 Network: TRC-20",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(
                f"💰 *PAY WITH USDT*\n\n"
                f"`{address}`\n\n"
                f"📱 Tap and hold the address to copy it.\n"
                f"⚠️ Send the EXACT amount to this address.\n"
                f"🌐 Network: TRC-20",
                parse_mode=ParseMode.MARKDOWN
            )
        await query.answer("USDT payment address shown!")
        return
    
    elif data.startswith("show_seller_"):
        escrow_id = data.replace("show_seller_", "")
        escrow = db.get_escrow(escrow_id)
        
        if escrow:
            seller_address = escrow[11]
            currency = escrow[4]
            
            qr_image = generate_qr_code(seller_address)
            
            if qr_image:
                await query.message.reply_photo(
                    photo=qr_image,
                    caption=f"📤 *SEND PAYMENT TO SELLER*\n\n"
                            f"💱 Currency: {currency}\n"
                            f"📱 Scan QR Code or copy the address below:\n\n"
                            f"`{seller_address}`\n\n"
                            f"📱 Tap and hold the address to copy it.\n"
                            f"⚠️ Double-check the address before sending!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.message.reply_text(
                    f"📤 *SEND PAYMENT TO SELLER*\n\n"
                    f"💱 Currency: {currency}\n"
                    f"`{seller_address}`\n\n"
                    f"📱 Tap and hold the address to copy it.\n"
                    f"⚠️ Double-check the address before sending!",
                    parse_mode=ParseMode.MARKDOWN
                )
            await query.answer("Seller address shown!")
            return
    
    elif data.startswith("payment_done_"):
        escrow_id = data.replace("payment_done_", "")
        escrow = db.get_escrow(escrow_id)
        
        if escrow:
            db.update_escrow_status(escrow_id, "paid")
            
            keyboard = [
                [InlineKeyboardButton("📊 View Escrow", callback_data=f"view_escrow_{escrow_id}")],
                [InlineKeyboardButton("🔐 Release Funds", callback_data=f"release_{escrow_id}")],
                [InlineKeyboardButton("🆘 Support", callback_data="support")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ]
            
            text = f"""✅ *PAYMENT MARKED AS SENT!*

📋 Escrow ID: `{escrow_id}`
💱 Currency: {escrow[4]}
💰 Amount: {escrow[5]} {escrow[4]}
👤 Seller: @{escrow[3]}

⏳ WHAT'S NEXT:

1️⃣ Wait for seller to deliver the goods/service
2️⃣ Confirm delivery with the seller
3️⃣ Release funds using the button below

⚠️ IMPORTANT:
Only release funds after you receive what you paid for!

Need help? Contact @oxymoronic01 with your Escrow ID."""
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.answer("Payment marked as sent!")
    
    elif data.startswith("release_"):
        escrow_id = data.replace("release_", "")
        escrow = db.get_escrow(escrow_id)
        
        if escrow:
            keyboard = [
                [InlineKeyboardButton("✅ Confirm Release", callback_data=f"confirm_release_{escrow_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"view_escrow_{escrow_id}")]
            ]
            
            text = f"""🔐 *RELEASE FUNDS CONFIRMATION*

📋 Escrow ID: `{escrow_id}`
💱 Currency: {escrow[4]}
💰 Amount: {escrow[5]} {escrow[4]}
👤 Seller: @{escrow[3]}
📤 Seller's Address: `{escrow[11]}`

⚠️ WARNING:
Releasing funds will mark this escrow as COMPLETED.
Only release if you have received the goods/service!

Confirm to release funds to the seller."""
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif data.startswith("confirm_release_"):
        escrow_id = data.replace("confirm_release_", "")
        escrow = db.get_escrow(escrow_id)
        
        if escrow:
            db.update_escrow_status(escrow_id, "completed")
            
            keyboard = [
                [InlineKeyboardButton("📊 My Escrows", callback_data="my_escrows")],
                [InlineKeyboardButton("🆘 Support", callback_data="support")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ]
            
            text = f"""✅ *FUNDS RELEASED SUCCESSFULLY!*

📋 Escrow ID: `{escrow_id}`
💱 Currency: {escrow[4]}
💰 Amount: {escrow[5]} {escrow[4]}
👤 Seller: @{escrow[3]}
📤 Seller's Address: `{escrow[11]}`

✅ Escrow Status: COMPLETED

📋 Transaction Complete!
• Payment sent to seller
• Goods/service delivered
• Escrow marked as complete

Thank you for using Crypto Escrow Bot!

Need help? Contact @oxymoronic01"""
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.answer("Funds released successfully!")
    
    elif data.startswith("view_escrow_"):
        escrow_id = data.replace("view_escrow_", "")
        await view_escrow_details(query, escrow_id)

async def view_escrow_details(query, escrow_id):
    """View escrow details"""
    escrow = db.get_escrow(escrow_id)
    
    if not escrow:
        await query.edit_message_text("❌ Escrow not found.")
        return
    
    btc_address = Config.YOUR_WALLETS.get("BTC")
    eth_address = Config.YOUR_WALLETS.get("ETH")
    ltc_address = Config.YOUR_WALLETS.get("LTC")
    doge_address = Config.YOUR_WALLETS.get("DOGE")
    usdt_address = Config.YOUR_WALLETS.get("USDT")
    
    # Get status with fallback
    status = escrow[7] if escrow[7] else "unknown"
    status_emoji = {
        "pending": "⏳",
        "paid": "💰",
        "completed": "✅",
        "cancelled": "❌"
    }.get(status, "❓")
    
    keyboard = []
    
    if status == "pending":
        keyboard.append([InlineKeyboardButton("💰 Pay with BTC", callback_data="pay_btc")])
        keyboard.append([InlineKeyboardButton("💰 Pay with ETH", callback_data="pay_eth")])
        keyboard.append([InlineKeyboardButton("💰 Pay with LTC", callback_data="pay_ltc")])
        keyboard.append([InlineKeyboardButton("💰 Pay with DOGE", callback_data="pay_doge")])
        keyboard.append([InlineKeyboardButton("💰 Pay with USDT", callback_data="pay_usdt")])
        keyboard.append([InlineKeyboardButton("✅ I've Made Payment", callback_data=f"payment_done_{escrow_id}")])
    if status == "paid":
        keyboard.append([InlineKeyboardButton("🔐 Release Funds", callback_data=f"release_{escrow_id}")])
    
    keyboard.append([InlineKeyboardButton("📤 Show Seller Address", callback_data=f"show_seller_{escrow_id}")])
    keyboard.append([InlineKeyboardButton("🆘 Support", callback_data="support")])
    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    
    # Get values with fallbacks
    escrow_id_val = escrow[0] if escrow[0] else "N/A"
    currency = escrow[4] if escrow[4] else "Unknown"
    amount = escrow[5] if escrow[5] else 0
    fee = escrow[6] if escrow[6] else 0
    total = escrow[8] if escrow[8] else 0
    seller_username = escrow[3] if escrow[3] else "Unknown"
    seller_address = escrow[11] if escrow[11] else "Not provided"
    created = escrow[9][:19] if escrow[9] else "N/A"
    completed = escrow[10][:19] if escrow[10] else "Not yet"
    
    text = f"""📋 *ESCROW DETAILS*

{status_emoji} Status: {status.upper()}

📋 Escrow ID: `{escrow_id_val}`
💱 Currency: {currency}
💰 Amount: {amount} {currency}
📊 Fee: {fee} {currency}
💵 Total: {total} {currency}
👤 Seller: @{seller_username}
📤 Seller Address: `{seller_address}`
📅 Created: {created}
📅 Completed: {completed}

━━━━━━━━━━━━━━━━━━━━━━

YOUR WALLET ADDRESSES:

💵 BTC: `{btc_address}`
💎 ETH: `{eth_address}`
🥇 LTC: `{ltc_address}`
🐕 DOGE: `{doge_address}`
💵 USDT: `{usdt_address}`

━━━━━━━━━━━━━━━━━━━━━━

QUICK ACTIONS:
• Click "Pay with [Currency]" to get payment address with QR code
• Click "Show Seller Address" to see seller's wallet with QR code
• Contact @oxymoronic01 for help"""
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def list_escrows(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all escrows for the user"""
    user_id = update.effective_user.id
    escrows = db.get_user_escrows(user_id)
    
    # Determine if this is a callback query or direct command
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_obj = query.message
    else:
        message_obj = update.message
    
    if not escrows:
        await message_obj.reply_text(
            "📊 *YOUR ESCROWS*\n\n"
            "No escrows found.\n"
            "Use /create to start your first escrow! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    text = "📊 *YOUR ESCROWS*\n"
    text += "═" * 30 + "\n\n"
    
    for escrow in escrows[:10]:
        status = escrow[7] if escrow[7] else "unknown"
        status_emoji = {
            "pending": "⏳",
            "paid": "💰",
            "completed": "✅",
            "cancelled": "❌"
        }.get(status, "❓")
        
        escrow_id = escrow[0] if escrow[0] else "N/A"
        seller_username = escrow[3] if escrow[3] else "Unknown"
        currency = escrow[4] if escrow[4] else "Unknown"
        amount = escrow[5] if escrow[5] else 0
        created_date = escrow[9][:10] if escrow[9] else "Unknown"
        
        text += f"{status_emoji} `{escrow_id}`\n"
        text += f"   💱 {currency} {amount:.8f}\n"
        text += f"   👤 @{seller_username}\n"
        text += f"   📅 {created_date}\n"
        text += f"   📌 Status: {status.upper()}\n"
        text += f"   🔗 /release {escrow_id}\n\n"
    
    if len(escrows) > 10:
        text += f"\n📌 Showing 10 of {len(escrows)} escrows"
    
    keyboard = [
        [InlineKeyboardButton("🆘 Need Help?", callback_data="support")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    await message_obj.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def release_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Release funds from escrow (manual command)"""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "🔐 *RELEASE FUNDS*\n\n"
            "Usage: /release <escrow_id>\n"
            "Example: /release abc12345\n\n"
            "Get your escrow ID from /list\n"
            "Or use /support for help.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    escrow_id = args[0]
    escrow = db.get_escrow(escrow_id)
    
    if not escrow:
        await update.message.reply_text(
            f"❌ Escrow `{escrow_id}` not found.\n\n"
            f"Please check the ID and try again.\n"
            f"Use /list to see your escrows.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if escrow[1] != user_id:
        await update.message.reply_text(
            "❌ You are not the buyer for this escrow.\n\n"
            "Only the buyer can release funds.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if escrow[7] != "paid":
        await update.message.reply_text(
            f"❌ Escrow status is `{escrow[7]}`. Cannot release.\n\n"
            f"Make sure you've marked payment as sent first!\n"
            f"Use /list to check your escrows.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    db.update_escrow_status(escrow_id, "completed")
    
    currency = escrow[4] if escrow[4] else "Unknown"
    seller_address = escrow[11] if escrow[11] else "Not provided"
    seller_username = escrow[3] if escrow[3] else "Unknown"
    amount = escrow[5] if escrow[5] else 0
    
    text = f"""✅ *FUNDS RELEASED SUCCESSFULLY!*

📋 Escrow ID: `{escrow_id}`
💱 Currency: {currency}
💰 Amount: {amount} {currency}
👤 Seller: @{seller_username}
📤 Seller's Wallet: `{seller_address}`

✅ Escrow Status: COMPLETED

⚠️ IMPORTANT - Manual Action Required:
1️⃣ Send {amount} {currency} to the seller's wallet above
2️⃣ Confirm with the seller they received the payment
3️⃣ Transaction is complete!

Thank you for using Crypto Escrow Bot!
Need help? Contact @oxymoronic01"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check all wallet balances"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "⛔️ *ACCESS DENIED*\n\n"
                "The /balance command is only available to administrators.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "⛔️ *ACCESS DENIED*\n\n"
                "The /balance command is only available to administrators.",
                parse_mode=ParseMode.MARKDOWN
            )
        return
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text("🔄 Checking wallet balances...")
    else:
        msg = await update.message.reply_text("🔄 Checking wallet balances...")
    
    text = "💰 *WALLET BALANCES*\n"
    text += "═" * 30 + "\n\n"
    
    total_usd_estimate = 0
    
    for currency, address in Config.YOUR_WALLETS.items():
        try:
            balance = wallet_manager.check_balance(currency)
            is_valid = wallet_manager.validate_address(currency, address)
            
            if currency == "USDT":
                balance_str = f"{balance:.2f}"
            else:
                balance_str = f"{balance:.8f}"
            
            emoji = {
                "BTC": "💵",
                "ETH": "💎",
                "LTC": "🥇",
                "DOGE": "🐕",
                "USDT": "💵"
            }.get(currency, "🪙")
            
            text += f"{emoji} *{currency}*\n"
            text += f"   Balance: `{balance_str}`\n"
            text += f"   Address: `{address[:10]}...{address[-6:]}`\n"
            text += f"   Status: {'✅ Valid' if is_valid else '❌ Invalid'}\n\n"
            
            if balance > 0:
                if currency == "BTC":
                    total_usd_estimate += balance * 43000
                elif currency == "ETH":
                    total_usd_estimate += balance * 2200
                elif currency == "LTC":
                    total_usd_estimate += balance * 70
                elif currency == "DOGE":
                    total_usd_estimate += balance * 0.08
                elif currency == "USDT":
                    total_usd_estimate += balance
            
        except Exception as e:
            logger.error(f"Error checking {currency}: {e}")
            text += f"❌ *{currency}*\n"
            text += f"   Error: Could not fetch balance\n\n"
    
    text += "═" * 30 + "\n"
    text += f"🔄 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    if total_usd_estimate > 0:
        text += f"\n💵 Estimated Total: ~${total_usd_estimate:.2f} USD"
    
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
🤖 *CRYPTO ESCROW BOT HELP*

*Available Commands:*

📝 `/create` - Start a new escrow
📊 `/list` - View your escrows  
🔐 `/release <id>` - Release funds from escrow
💰 `/balance` - Check wallet balances (admin only)
🆘 `/support` - Contact support
❌ `/cancel` - Cancel current operation
ℹ️ `/help` - Show this help

*How Escrow Works:*

1️⃣ *Create Escrow*
   • Select currency
   • Enter seller's username
   • Enter seller's wallet address
   • Enter amount
   • Confirm details

2️⃣ *Make Payment*
   • Click "Pay with [Currency]"
   • Scan QR code or copy address
   • Send exact amount
   • Click "I've Made Payment"

3️⃣ *Complete Trade*
   • Seller delivers goods/service
   • Use /release to confirm
   • Send funds manually

*Supported Currencies:*
💰 BTC • ETH • LTC • DOGE • USDT

*Fee Structure:*
📊 {Config.ESCROW_FEE}% of transaction amount

*Security:*
🔐 All transactions are tracked
🛡️ Dispute resolution available
📋 Escrow IDs for reference

*Need Help?*
Contact @oxymoronic01 (Response: ~10 mins)
    """
    
    keyboard = [
        [InlineKeyboardButton("📝 Create Escrow", callback_data="create_escrow")],
        [InlineKeyboardButton("📊 My Escrows", callback_data="my_escrows")],
        [InlineKeyboardButton("🆘 Support", callback_data="support")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation and return to start"""
    user_id = update.effective_user.id
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        
        await query.edit_message_text(
            "❌ Operation Cancelled\n\nYou've been returned to the main menu."
        )
        await start(update, context)
    else:
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        
        await update.message.reply_text(
            "❌ Operation Cancelled\n\nYou've been returned to the main menu."
        )
        await start(update, context)

async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to home menu"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    user_id = query.from_user.id
    if user_id in USER_STATES:
        del USER_STATES[user_id]
    
    await query.edit_message_text(
        "🏠 Returning to main menu..."
    )
    
    await start(update, context)

def run_bot():
    """Run the Telegram bot"""
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("create", create_escrow))
    application.add_handler(CommandHandler("release", release_funds))
    application.add_handler(CommandHandler("list", list_escrows))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(create_escrow, pattern="^create_escrow$"))
    application.add_handler(CallbackQueryHandler(handle_currency, pattern="^cur_"))
    application.add_handler(CallbackQueryHandler(confirm_escrow, pattern="^confirm_escrow$"))
    application.add_handler(CallbackQueryHandler(handle_payment_actions, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(handle_payment_actions, pattern="^show_"))
    application.add_handler(CallbackQueryHandler(handle_payment_actions, pattern="^payment_done_"))
    application.add_handler(CallbackQueryHandler(handle_payment_actions, pattern="^release_"))
    application.add_handler(CallbackQueryHandler(handle_payment_actions, pattern="^confirm_release_"))
    application.add_handler(CallbackQueryHandler(handle_payment_actions, pattern="^view_escrow_"))
    application.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    application.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    application.add_handler(CallbackQueryHandler(list_escrows, pattern="^my_escrows$"))
    application.add_handler(CallbackQueryHandler(balance, pattern="^balance$"))
    application.add_handler(CallbackQueryHandler(home, pattern="^home$"))
    
    # Message handler for text input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running with YOUR wallets only (no generation)...")
    print(f"✅ Admin ID: {Config.ADMIN_IDS}")
    print(f"✅ Supported currencies: BTC, ETH, LTC, DOGE, USDT")
    print("✅ Bot is ready! Send /start to get started.")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    run_bot()