pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                cleanWs()
                git branch: 'main',
                    url: 'https://github.com/hana-sellami18/gestion-stagiaires-ai.git'
            }
        }
        stage('Push to Hugging Face') {
            steps {
                withCredentials([string(credentialsId: 'HF_TOKEN', variable: 'HF_TOKEN')]) {
                    bat '''
                        git remote remove hf || true
                        git remote add hf https://HANA20:%HF_TOKEN%@huggingface.co/spaces/HANA20/asm-ia
                        git push hf main --force
                    '''
                }
            }
        }
        stage('Wait for Build') {
            steps {
                bat 'ping -n 121 127.0.0.1 > nul'
            }
        }
        stage('Health Check') {
            steps {
                retry(3) {
                    bat 'ping -n 31 127.0.0.1 > nul'
                    bat 'curl -f https://hana20-asm-ia.hf.space/health'
                }
            }
        }
    }
}
