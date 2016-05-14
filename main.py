#!python
import os.path as path
import cherrypy

class Root:
    @cherrypy.expose
    def index(self):
        return """<html>
                <head>
                    <title>CherryPy static tutorial</title>
                </head>
                <html>
                <body>
                <a href="feed/notes.rss">RSS 2.0</a>
                <br />
                <a href="feed/notes.atom">Atom 1.0</a>
                </body>
                </html>"""

if __name__ == '__main__':

    current_dir = path.dirname(path.abspath(__file__))

    # Set up site-wide config first so we get a log if errors occur.
    cherrypy.config.update({'environment': 'production',
                            'log.error_file': 'site.log',
                            'log.screen': True})

    conf = {'/': {'tools.staticdir.on': True,
                  'tools.staticdir.dir': path.join(current_dir, 'datafiles')}}

    cherrypy.quickstart(Root(), '/', config=conf)

