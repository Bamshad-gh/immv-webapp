from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField' 
    # what type of automatic ID Django creates for every model row
    
    name = 'users'  # tells Django which app folder this config belongs to 
                    # must match your app folder name exactly 

    def ready(self):
        """
        This method runs automatically when Django starts up.
        We use it to load our signals file so Django knows about our signals.
        Without this, signals.py is NEVER loaded and signals never fire.
        """
        import users.signals            # load the signals file on startup
