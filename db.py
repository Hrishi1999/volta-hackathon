import marqo
import click
import json

@click.group()
def cli():
    """Marqo Database CLI Operations"""
    pass

@cli.command()
@click.option('--title', required=True, help='Document title')
@click.option('--description', required=True, help='Document description')
@click.option('--id', 'doc_id', help='Optional document ID')
def add(title, description, doc_id):
    """Add a document to the Marqo index"""
    mq = marqo.Client(url='http://localhost:8882')
    
    document = {
        "Title": title,
        "Description": description
    }
    
    if doc_id:
        document["_id"] = doc_id
        
    mq.index("my-first-index").add_documents(
        [document],
        tensor_fields=["Description"]
    )
    click.echo(f"Added document: {title}")

@cli.command()
@click.option('--query', required=True, help='Search query')
def search(query):
    """Search documents in the Marqo index"""
    mq = marqo.Client(url='http://localhost:8882')
    results = mq.index("my-first-index").search(q=query)
    click.echo(json.dumps(results, indent=2))

if __name__ == '__main__':
    cli()




