import os
import subprocess


def setup_project():
    print('Instalando dependências...')
    subprocess.run(['pdm', 'install'], check=True, shell=False)

    env_file = '.env'
    if not os.path.exists(env_file):
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write('MODE=DEVELOPMENT\n')
            f.write('DEBUG=True\n')
            f.write('SECRET_KEY=exemplo\n')
            f.write('CLOUDINARY_URL=cloudinary://exemplo.com/media/\n')
            f.write('EMAIL_HOST_USER=seu@email.com\n')
            f.write('EMAIL_HOST_PASSWORD=\n')
            f.write('EMAIL_HOST=\n')
            f.write('DEFAULT_FROM_EMAIL=seu@email.com\n')
            f.write('FRONTEND_URL=http://localhost:5173\n')
            f.write('FRONTEND_ADMIN_URL=\n')
        print()
        print(f'Arquivo {env_file} criado com variáveis padrão.')
    else:
        print()
        print(f'O arquivo {env_file} já existe. Pulando criação.')

    print()
    print('Preparando banco de dados...')
    subprocess.run(
        ['pdm', 'run', 'python', 'manage.py', 'makemigrations', 'uploader', 'router', 'authenticator'],
        check=True,
        shell=False,
    )

    subprocess.run(['pdm', 'run', 'python', 'manage.py', 'migrate'], check=True, shell=False)

    print()
    print('Gerando MER...')
    result = subprocess.run(
        [
            'pdm',
            'run',
            'python',
            'manage.py',
            'graph_models',
            '--pydot',
            '--arrow-shape',
            'normal',
            '--color-code-deletions',
            '--hide-edge-labels',
            '--disable-sort-fields',
            '-S',
            '-g',
            '-o',
            'core.png',
            'authenticator',
            'uploader',
            'router',
        ],
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        print('Não foi possível gerar o MER (requer o pacote "pydot" e o Graphviz instalado). Pulando essa etapa.')


if __name__ == '__main__':
    setup_project()
