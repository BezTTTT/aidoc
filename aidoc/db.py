import mysql.connector
from flask import current_app, g
import click
import os

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            database=current_app.config['DB_DATABASE'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD']
        )
        g.db.autocommit = True
    
    return (g.db, g.db.cursor(dictionary=True))

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

@click.command('init-db')
def init_db():
    db, cursor = get_db()
    cursor.execute("SHOW TABLES")
    if cursor.fetchone() is None:
        click.echo('Initializing the database: ')
        projectDir = os.path.dirname(current_app.root_path)
        with open(os.path.join(projectDir, 'schema.sql'), encoding="utf8") as f:
            cursor.execute(f.read(), multi=True)
        close_db()

        db, cursor = get_db()
        cursor.execute(current_app.config['ADMIN_USER_INSERT_SQL']) # Insert Admin user into the user table
        cursor.execute("SHOW TABLES")
        if cursor.fetchone() is None:
            click.echo('... Failed to initialize the database.')
        else:
            click.echo('... Successfully.')
    else:
        click.echo('The tables already exists.')

  
def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db)