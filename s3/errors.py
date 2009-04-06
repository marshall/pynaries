class S3Error(Exception):
    def __init__(self, code='', message='', resource=''):
        Exception.__init__(self)
        self.code = code
        self.message = message
        self.resource = resource
    
    def __str__(self):
        return 'S3Error: %s - %s\n%s' % (self.code, self.message, self.resource)
    
    def __repr__(self):
        return '%s: %s\n%s' % (self.code, self.message, self.resource)
