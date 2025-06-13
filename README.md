# Grizz-AI

An AI-powered application for generating comics, processing media, and creating content.

## Setup Instructions

### 1. Environment Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your actual API keys and configuration values:
```bash
nano .env  # or use your preferred editor
```

### 2. Required API Keys

You'll need to obtain API keys from the following services:

- **OpenAI**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Perplexity**: Get your API key from [Perplexity AI](https://www.perplexity.ai/settings/api)
- **ElevenLabs**: Get your API key from [ElevenLabs](https://elevenlabs.io/app/settings/api-keys)
- **Groq**: Get your API key from [Groq Console](https://console.groq.com/keys)
- **OpenRouter**: Get your API key from [OpenRouter](https://openrouter.ai/keys)
- **Brave Search**: Get your API key from [Brave Search API](https://api.search.brave.com/app/keys)
- **Hugging Face**: Get your API key from [Hugging Face](https://huggingface.co/settings/tokens)

### 3. Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up the database:
```bash
python src/database.py
```

3. Run the application:
```bash
python src/main.py
```

## Security Notice

- **Never commit your `.env` file or any files containing API keys**
- The `.gitignore` file is configured to exclude sensitive files
- Always use environment variables for secrets in production
- Regularly rotate your API keys

## Project Structure

- `src/` - Main application code
- `src/modules/` - Modular components
- `src/templates/` - HTML templates
- `src/static/` - Static files (CSS, JS, images)
- `data/` - Database files (excluded from git)
- `logs/` - Log files (excluded from git)
- `output/` - Generated content (excluded from git)

## Features

- Comic generation using AI
- Media processing capabilities
- User authentication and loyalty system
- Social media integration
- Voice recognition and synthesis
- Image generation and processing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure no secrets are committed
5. Submit a pull request

## License

[Add your license information here]
