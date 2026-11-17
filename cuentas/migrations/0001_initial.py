import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models



class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Usuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('correo', models.EmailField(max_length=254, unique=True, verbose_name='correo electrónico')),
                ('nombre', models.CharField(max_length=150, verbose_name='nombre')),
                ('es_empresa', models.BooleanField(default=False, verbose_name='es empresa')),
                ('is_active', models.BooleanField(default=False, verbose_name='activa')),
                ('is_staff', models.BooleanField(default=False, verbose_name='acceso al panel de administración')),
                ('correo_verificado_en', models.DateTimeField(blank=True, null=True, verbose_name='correo verificado en')),
                ('fecha_registro', models.DateTimeField(default=django.utils.timezone.now, verbose_name='fecha de registro')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'usuario',
                'verbose_name_plural': 'usuarios',
            },
        ),
        migrations.CreateModel(
            name='Empresa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rfc', models.CharField(max_length=13, verbose_name='RFC o registro fiscal')),
                ('usuario', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='empresa', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'empresa',
                'verbose_name_plural': 'empresas',
            },
        ),
        migrations.CreateModel(
            name='EnlaceVerificacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('expira_en', models.DateTimeField()),
                ('usado_en', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enlaces_verificacion', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'enlace de verificación',
                'verbose_name_plural': 'enlaces de verificación',
            },
        ),
    ]
