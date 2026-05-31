pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/hana-sellami18/gestion-stagiaires-ai.git'
            }
        }

        stage('Build Docker Image') {
            steps {
                bat 'docker build -t asm-ia:1.0 .'
            }
        }

        stage('Verify Image') {
            steps {
                bat 'docker images asm-ia:1.0'
            }
        }

        stage('Deploy') {
            steps {
                bat '''
                    docker stop asm-ia || true
                    docker rm asm-ia || true
                    docker run -d --name asm-ia --network asm-network -p 8000:8000 --env-file C:/ProgramData/Jenkins/.jenkins/ia.env asm-ia:1.0
                '''
            }
        }

        stage('Health Check') {
            steps {
                bat 'ping -n 31 127.0.0.1 > nul && docker ps | findstr asm-ia'
            }
        }
    }
}