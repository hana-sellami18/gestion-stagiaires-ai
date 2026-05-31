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
                sh 'docker build -t asm-ia:1.0 .'
            }
        }

        stage('Verify Image') {
            steps {
                sh 'docker images asm-ia:1.0'
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    docker stop asm-ia || true
                    docker rm asm-ia || true
                    docker run -d --name asm-ia \
                        --network asm-network \
                        -p 8000:8000 \
                        --env-file /var/jenkins_home/ia.env \
                        asm-ia:1.0
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh 'sleep 30 && docker ps | grep asm-ia'
            }
        }
    }
}