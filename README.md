# Grizzly Grill Smokes: Food Truck and Catering Service with Entertainment

Grizzly Grill Smokes is a unique food truck and catering service that offers delicious BBQ cuisine along with entertaining features like AI-generated comics and a curated music selection for our customers.

## Key Features

1. Food Truck and Catering Services
   - Delicious BBQ menu items
   - Catering options for events
   - Online food menu display

2. Entertainment Features
   - AI-generated daily comics based on local events
   - Custom comic creation for special occasions
   - Curated music playlist for a great dining atmosphere

3. User Experience
   - Easy-to-use web interface for browsing menu, comics, and music
   - User accounts for personalized experiences
   - Mobile-responsive design for on-the-go access

4. Admin Features
   - Menu management system
   - Comic generation and moderation tools
   - Music playlist management

## Tech Stack

- Backend: Python with Flask web framework
- Database: SQLite (with potential for easy migration to PostgreSQL)
- Frontend: HTML, CSS, JavaScript with Jinja2 templating
- AI Integration: OpenAI GPT, DALL-E for comic generation
- Authentication: Custom implementation with session management

## Project Setup

1. Clone the repository
2. Create a virtual environment: `python3 -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (on Unix) or `venv\Scripts\activate` (on Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables in a `.env` file (see Configuration section)
6. Run the web application: `python src/web_app.py`

## Configuration

Create a `.env` file in the project root with the following variables:

```
SECRET_KEY=your_secret_key
ADMIN_PASSWORD=your_admin_password
OUTPUT_DIR=path_to_output_directory
WEB_PORT=5000
WEB_DEBUG=True
GENERATE_AUDIO=True
```

Adjust the values according to your setup and requirements.

## Usage

1. Start the web application by running `python src/web_app.py`
2. Navigate to the provided local URL (typically `http://localhost:5000`)
3. Browse the food menu, view daily comics, and check out the music playlist
4. For catering inquiries, use the provided contact information

## Contributing

Contributions to Grizzly Grill Smokes are welcome. Please ensure to follow the coding standards and submit pull requests for any new features or bug fixes.

## License

[Add appropriate license information here]

For more information or support, please contact [add contact information].
