// Função para inicializar todos os modais do Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    // Inicializa todos os modais
    document.querySelectorAll('.modal').forEach(modalElement => {
        new bootstrap.Modal(modalElement);
    });
}); 