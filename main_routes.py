from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ext import db
from forms import LoginForm, RegisterForm, PostForm
from models import Post, User
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from models import Setting

def time_chat():
    first_setting = Setting.query.first()
    if not first_setting:
        return jsonify({
            "success": False,
            "error": "Settings not found."
        }), 500

    RATE_LIMIT_SECONDS = first_setting.rate_limit_seconds 
    



def is_admin(user):
    """ by D7fex ამოწმებს არის თუ არა მომხმარებელი ადმინი."""
    return getattr(user, 'role', 'User') == 'Admin'

def is_moderator_or_admin(user):
    """by D7fex ამოწმებს არის თუ არა მომხმარებელი მოდერატორი ან ადმინი."""
    return is_admin(user) or getattr(user, 'role', 'User') == 'Moderator'

def get_user_by_username(username):
    """პოულობს მომხმარებელს მომხმარებლის სახელით, რეგისტრის იგნორირებით by D7fex"""
    return User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first()

def create_system_post(message, db):
    """ქმნის სისტემურ შეტყობინებას Post ცხრილში (user_id=None)  by D7fex"""
    new_post = Post(user_message=message, user_id=None, is_system=True)
    db.session.add(new_post)
    try:
        db.session.commit()
        return {
            "success": True,
            "post_id": new_post.id,
            "user_message": new_post.user_message,
            "author_username": "SYSTEM",
            "author_role": "System",
            "author_color": 'u-system',  # Use the correct class for system messages

            "is_system": True,
            "created_at": new_post.created_at.strftime('%Y-%m-%d %H:%M')
        }
    except Exception as e:
        db.session.rollback()
        print(f"Error creating system post: {e}")
        return {"success": False, "error": f"Database error creating system post: {e}"}


def handle_command(message, current_user, db):
    """ამუშავებს ყველა ჩატის ბრძანებას by D7FEX """
    parts = message.split(' ', 1)
    command = parts[0].lower() 
    args = parts[1].strip() if len(parts) > 1 else ""
    arg_parts = args.split(' ')
    
    now = datetime.utcnow()
 # --- /timeout COMMAND ---
    if command == '/timeout':
        if not is_admin(current_user):
            return jsonify({"success": False, "error": "Permission denied. Only Admins can set the timeout."}), 403
        
        if not args or not args.replace('.', '', 1).isdigit():
            return jsonify({"success": False, "error": "Usage: /timeout <seconds> (e.g., /timeout 0.5)"}), 400
        
        try:
            timeout_seconds = float(args)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid timeout value."}), 400
        
        # Update the global rate limit in the Setting model
        first_setting = Setting.query.first()
        if first_setting:
            first_setting.rate_limit_seconds = timeout_seconds
            db.session.commit()
            system_message = f"Global chat timeout set to {timeout_seconds} seconds by Admin **{current_user.username}**."
            return jsonify(create_system_post(system_message, db)), 200
        else:
            return jsonify({"success": False, "error": "Settings not found."}), 500

    # --- MUTE CHECK ---
    # Allow /clear and /color even if muted
    if current_user.is_muted and command not in ['/clear', '/color']:
        if current_user.mute_until and current_user.mute_until < now:
            # Mute expired
            current_user.is_muted = False
            current_user.mute_until = None
            db.session.commit()
        else:
            # Still muted
            mute_msg = f"You are muted. Please wait until {current_user.mute_until.strftime('%Y-%m-%d %H:%M UTC')}" if current_user.mute_until else "You are permanently muted."
            return jsonify({"success": False, "error": mute_msg}), 403
    
    # --- REGULAR COMMANDS ---
    
    if command == '/clear':
        # This command is handled client-side
        return jsonify({"success": True, "command": "clear_log"}), 200

    if command == '/color':
        if not args:
            return jsonify({"success": False, "error": "Usage: /color <color_name>"}), 400
        
        color_name = arg_parts[0].lower()
        allowed_colors = ['green', 'blue', 'pink', 'purple', 'cyan', 'gray', 'black', 'neon']
        
        # Moderator and Admin colors are reserved
        if is_moderator_or_admin(current_user):
            allowed_colors.append('moderator')
        if is_admin(current_user):
            allowed_colors.append('admin')

        if color_name not in allowed_colors:
            return jsonify({"success": False, "error": f"Invalid color. Available: {', '.join(allowed_colors)}"}), 400
        
        current_user.custom_color_class = f'u-{color_name}'
        db.session.commit()
        
        # Inform the chat via a system message
        system_message = f"User **{current_user.username}**'s color changed to {color_name}."
        return jsonify(create_system_post(system_message, db)), 200


    # --- MODERATOR/ADMIN COMMANDS ---

    if command == '/say':
        if not is_admin(current_user):
            return jsonify({"success": False, "error": "Permission denied. Only Admins can use /say."}), 403

        if not args:
            return jsonify({"success": False, "error": "Usage: /say <message>"}), 400
        
        # Post as SYSTEM for an announcement
        system_message = f"**Announcement **: {args}"
        return jsonify(create_system_post(system_message, db)), 200

    if command == '/mute':
        if not is_moderator_or_admin(current_user):
            return jsonify({"success": False, "error": "Permission denied. Only Mods/Admins can mute."}), 403
        
        if len(arg_parts) < 2 or not arg_parts[1].isdigit():
            return jsonify({"success": False, "error": "Usage: /mute <username> <minutes> (e.g., /mute john 30)"}), 400

        target_username = arg_parts[0]
        try:
            mute_duration_minutes = int(arg_parts[1])
        except ValueError:
            return jsonify({"success": False, "error": "Mute duration must be an integer in minutes."}), 400

        target_user = get_user_by_username(target_username)
        if not target_user:
            return jsonify({"success": False, "error": f"User '{target_username}' not found."}), 404
        
        # Security check: Prevent muting higher/equal roles unless current user is Admin
        if is_moderator_or_admin(target_user) and not is_admin(current_user):
             return jsonify({"success": False, "error": "You cannot mute another Moderator or Admin."}), 403
        if is_admin(target_user) and current_user.id != target_user.id:
            return jsonify({"success": False, "error": "Cannot mute an Admin unless self-muting."}), 403
        
        mute_until = now + timedelta(minutes=mute_duration_minutes)

        target_user.is_muted = True
        target_user.mute_until = mute_until
        db.session.commit()

        system_message = f"User **{target_username}** has been muted for {mute_duration_minutes} minutes by **{current_user.username}**."
        return jsonify(create_system_post(system_message, db)), 200

    if command == '/unmute':
        if not is_moderator_or_admin(current_user):
            return jsonify({"success": False, "error": "Permission denied. Only Mods/Admins can unmute."}), 403
        
        if not args:
            return jsonify({"success": False, "error": "Usage: /unmute <username>"}), 400

        target_username = arg_parts[0]
        target_user = get_user_by_username(target_username)

        if not target_user:
            return jsonify({"success": False, "error": f"User '{target_username}' not found."}), 404
        
        if not target_user.is_muted:
            return jsonify({"success": False, "error": f"User '{target_username}' is not currently muted."}), 400

        target_user.is_muted = False
        target_user.mute_until = None
        db.session.commit()

        system_message = f"User **{target_username}** has been unmuted by **{current_user.username}**."
        return jsonify(create_system_post(system_message, db)), 200

    # --- ADMIN COMMANDS ---

    if command == '/setmod':
        if not is_admin(current_user):
            return jsonify({"success": False, "error": "Permission denied. Only Admins can set roles."}), 403

        if not args:
            return jsonify({"success": False, "error": "Usage: /setmod <username>"}), 400

        target_username = arg_parts[0]
        target_user = get_user_by_username(target_username)

        if not target_user:
            return jsonify({"success": False, "error": f"User '{target_username}' not found."}), 404
        
        if target_user.role == 'Admin':
             return jsonify({"success": False, "error": "User is already an Admin."}), 400
        
        target_user.role = 'Moderator'
        db.session.commit()

        system_message = f"User **{target_username}** has been promoted to **Moderator** by **{current_user.username}**."
        return jsonify(create_system_post(system_message, db)), 200
    
    if command == '/removemod':
        if not is_admin(current_user):
            return jsonify({"success": False, "error": "Permission denied. Only Admins can set roles."}), 403

        if not args:
            return jsonify({"success": False, "error": "Usage: /removemod <username>"}), 400

        target_username = arg_parts[0]
        target_user = get_user_by_username(target_username)

        if not target_user:
            return jsonify({"success": False, "error": f"User '{target_username}' not found."}), 404
        
        if target_user.role == 'Admin':
            return jsonify({"success": False, "error": "Cannot demote an Admin."}), 400
        
        target_user.role = 'User'
        db.session.commit()

        system_message = f"User **{target_username}** has been demoted to **User** by **{current_user.username}**."
        return jsonify(create_system_post(system_message, db)), 200

    return jsonify({"success": False, "error": f"Unknown command: {command}. Use /help for available commands."}), 400


def register_routes(app):

    @app.route("/" , methods=["GET", "POST"])
    @login_required
    def home():
        current_chatters = User.query.all()
        form = PostForm()
        posts = Post.query.order_by(Post.created_at.asc()).all()
        return render_template("index.html", form=form, posts=posts, chatters=current_chatters)

    @app.route("/login", methods=["POST", "GET"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("home"))  
    
        form = LoginForm()
        
        if form.validate_on_submit():
            # Fetch the user from the database based on the username
            user = User.query.filter(User.username == form.username.data).first()
            
            # Check if the user exists and the password matches
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)  # Log the user in
                return redirect(url_for("home"))  # Redirect to home page after login
    
            # If login fails, you can add a flash message
            flash("Invalid username or password.", "danger")
        
        return render_template("login.html", form=form)

    @app.route("/register", methods=["POST", "GET"])
    def register():
        form = RegisterForm()
    
        if form.validate_on_submit():
            username = form.username.data
            password = form.password.data
            confirm_password = form.confirm_password.data

    
            existing_user = User.query.filter(User.username == username).first()
            if existing_user:
                print("sadasddddd")
                flash("Username already exists!", "danger")  
                return render_template('register.html', form=form)  
    
            elif password != confirm_password:
                print("sadasda")
                flash("Passwords do not match!", "danger")  
                return render_template('register.html', form=form) 
            else :
                print("finish")
                hashed_password = generate_password_hash(password)
        
                new_user = User(username=username, password=hashed_password, role='User')
                db.session.add(new_user)
                db.session.commit()
        
                login_user(new_user)
                flash("Registration successful! Welcome!", "success")  
                return redirect(url_for("home")) 
    
        return render_template("register.html", form=form)



    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("home"))

    @app.route("/upload_post", methods=["POST"])
    @login_required
    def upload_post():
        message = request.form.get('message', '').strip()
    
        # --- 1. COMMAND CHECK ---
        if message.startswith('/'):
            return handle_command(message, current_user, db)
        
        # --- 2. REGULAR POST VALIDATION ---
        if not message:
            return jsonify({"success": False, "error": "Message cannot be empty!"}), 400
    
        if len(message) > 200:
            return jsonify({"success": False, "error": "Message is too long (max 200 characters)!"}), 400
    
        # --- 3. CHECK IF USER IS MUTED ---
        if current_user.is_muted:
            if current_user.mute_until and current_user.mute_until > datetime.utcnow():
                remaining_time = (current_user.mute_until - datetime.utcnow()).total_seconds()
                return jsonify({
                    "success": False,
                    "error": f"You are muted! Please wait until {current_user.mute_until.strftime('%Y-%m-%d %H:%M UTC')}. Remaining time: {remaining_time:.1f} seconds."
                }), 403
            else:
                current_user.is_muted = False
                current_user.mute_until = None
                db.session.commit()
    
        # --- 4. RATE LIMIT CHECK ---
        now = datetime.utcnow()
        first_setting = Setting.query.first()
        if first_setting:
            RATE_LIMIT_SECONDS = first_setting.rate_limit_seconds
        else:
            RATE_LIMIT_SECONDS = 1.0  # Default to 1 second if no setting found
    
        if hasattr(current_user, 'last_post_time') and current_user.last_post_time:
            time_since_last_post = now - current_user.last_post_time
            if time_since_last_post < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining_time = (timedelta(seconds=RATE_LIMIT_SECONDS) - time_since_last_post).total_seconds()
                return jsonify({
                    "success": False,
                    "error": f"You are posting too fast! Please wait {remaining_time:.1f} seconds."
                }), 429
    
        # --- 5. CREATE POST ---
        new_post = Post(user_message=message, user_id=current_user.id)
        
        # Determine custom color class
        custom_color_class = current_user.custom_color_class or 'u-blue'  
    
        # Save the post to the database
        db.session.add(new_post)
        current_user.last_post_time = now
        db.session.commit()
    
        return jsonify({
            "success": True,
            "post_id": new_post.id,
            "user_message": new_post.user_message,
            "author_username": current_user.username,
            "author_role": getattr(current_user, 'role', 'User'),
            "author_color": custom_color_class,  # Add author color class here
            "created_at": new_post.created_at.strftime('%Y-%m-%d %H:%M')
        })
        
    @app.route("/get_new_posts/<int:last_post_id>")
    @login_required
    def get_new_posts(last_post_id):

        # Fetching posts must include system and emote posts as well
        new_posts = Post.query.filter(Post.id > last_post_id).order_by(Post.created_at.asc()).all()
        posts_data = []
        max_id = last_post_id

        for post in new_posts:

            # Determine author info for all post types (regular, system, emote)
            if post.is_system:
                author_username = "SYSTEM"
                author_role = "System"
                custom_color_class = 'u-system'
            else:

                # Regular or Emote post
                author_username = post.author.username if post.author else "Deleted User"
                author_role = getattr(post.author, 'role', 'User') if post.author else 'User'
                custom_color_class = getattr(post.author, 'custom_color_class', '') if post.author else ''

            posts_data.append({
    "id": post.id,
    "user_message": post.user_message,
    "author_username": author_username,
    "author_role": author_role,
    "author_color": custom_color_class,   
    "is_system": post.is_system,
    "is_emote": post.is_emote,
    "created_at": post.created_at.strftime('%Y-%m-%d %H:%M')
            })
            max_id = max(max_id, post.id)

        return jsonify({
            "posts": posts_data,
            "last_id": max_id
        })
