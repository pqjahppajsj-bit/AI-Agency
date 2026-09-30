# AI Agency

AI-powered business management and automation platform.

## Product

AI Agency is a web-based business platform designed to help businesses manage
core operations from one system.

The platform combines business management features with AI assistance,
customer accounts, products, orders, leads, payments and business-facing
dashboards.

## Core Features

- Business management
- Admin authentication
- Customer signup and login
- Customer dashboard
- Product management
- Order management
- Lead management
- Payment submission and payment-status management
- AI business assistant
- AI-powered business insights/follow-ups
- Public product pages
- Services, pricing, contact, privacy, terms and refund pages
- Business activation
- Android application source/build
- Production deployment configuration
- Gunicorn support
- Flask + SQLAlchemy backend
- SQLite database

## AI Integration

The platform includes an AI engine connected through the OpenAI Responses API.

The AI assistant is designed for practical business operations including:

- customers
- leads
- orders
- sales
- workflows
- business operations

AI API usage requires an API account with available credits. API credentials
are configured through environment variables and are not included in the
repository.

## Technology

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- SQLite
- Gunicorn
- Redis-compatible rate-limit configuration
- Python dotenv
- Android application
- OpenAI Responses API

## Configuration

Important environment variables include:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH`
- `FLASK_SECRET_KEY`
- `PRODUCTION`
- `RATELIMIT_STORAGE_URI`

Never commit `.env` or API credentials.

## Database

The current application uses SQLite and the production application database
is configured through the Flask SQLAlchemy configuration.

Database files are intentionally excluded from Git so customer/business data
and runtime data are not distributed with the source repository.

## Deployment

The project includes:

- `gunicorn.conf.py`
- `start_production.sh`
- production configuration
- Flask application
- templates
- static assets
- Android application source

## Acquisition / Transfer

The project is intended to be transferable to a new owner.

A buyer can receive the application source, deployment configuration,
documentation and Android source as part of an acquisition, subject to the
final transaction terms.

Third-party services, API accounts, hosting accounts and credentials should
be transferred or replaced by the buyer during handover rather than sharing
the seller's private credentials.

## Current Development Status

The platform has a functional web application, customer-facing features,
business management features, AI integration and Android application source.

The AI integration requires an API account with available usage credits for
live AI responses.

## Security

Do not publish:

- API keys
- passwords
- Flask secret keys
- database files containing customer data
- private deployment credentials

## License

Copyright © 2026. All rights reserved.

Transfer of ownership and licensing rights are determined by the final
acquisition agreement.
