import mysql.connector
from flask import current_app, g
import click
import os

# def get_db():
#     if 'db' not in g:
#         g.db = mysql.connector.connect(
#             host=current_app.config['DB_HOST'],
#             database=current_app.config['DB_DATABASE'],
#             user=current_app.config['DB_USER'],
#             password=current_app.config['DB_PASSWORD'],
#             port=current_app.config['DB_PORT']
#         )
#         g.db.autocommit = True
    
#     return (g.db, g.db.cursor(dictionary=True,buffered=True))

# def close_db(e=None):
#     db = g.pop('db', None)

#     if db is not None:
#         db.close()
        
def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            database=current_app.config['DB_DATABASE'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
        )
        g.db.autocommit = True
    
    return (g.db, g.db.cursor(dictionary=True,buffered=True))

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def get_db_risk_oca():
    if 'db_risk_oca' not in g:
        g.db_risk_oca = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            database=current_app.config['DB_DATABASE_RISK_OCA'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
        )
        g.db_risk_oca.autocommit = True
    
    return (g.db_risk_oca, g.db_risk_oca.cursor(dictionary=True,buffered=True))
        
def close_db_risk_oca(e=None):
    db = g.pop('db_risk_oca', None)

    if db is not None:
        db.close()

def get_db_2():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            database=current_app.config['DB_DATABASE_2'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD']
        )
        g.db.autocommit = True
    
    return (g.db, g.db.cursor(dictionary=True,buffered=True))

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()
        
def get_db_3():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            database=current_app.config['DB_DATABASE_3'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD']
        )
        g.db.autocommit = True
    
    return (g.db, g.db.cursor(dictionary=True,buffered=True))

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
            cursor.execute(f.read())
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