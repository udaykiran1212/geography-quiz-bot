// Initialize map
const map = L.map('map').setView([0, 0], 2);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// State management
let currentUser = null;
let currentQuestion = null;
let score = 0;

// DOM Elements
const loginBtn = document.getElementById('loginBtn');
const registerBtn = document.getElementById('registerBtn');
const authModal = document.getElementById('auth-modal');
const modalTitle = document.getElementById('modal-title');
const authForm = document.getElementById('auth-form');
const closeBtn = document.querySelector('.close');
const questionText = document.getElementById('question-text');
const optionsContainer = document.getElementById('options-container');
const scoreElement = document.getElementById('score');

// Event Listeners
loginBtn.addEventListener('click', () => showAuthModal('login'));
registerBtn.addEventListener('click', () => showAuthModal('register'));
closeBtn.addEventListener('click', () => hideAuthModal());
authForm.addEventListener('submit', handleAuthSubmit);

// Authentication Functions
function showAuthModal(type) {
    modalTitle.textContent = type === 'login' ? 'Login' : 'Register';
    authModal.style.display = 'block';
}

function hideAuthModal() {
    authModal.style.display = 'none';
}

async function handleAuthSubmit(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const isLogin = modalTitle.textContent === 'Login';

    try {
        const response = await fetch(`/api/auth/${isLogin ? 'login' : 'register'}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();
        if (response.ok) {
            currentUser = data.user;
            localStorage.setItem('token', data.token);
            hideAuthModal();
            loadNextQuestion();
        } else {
            alert(data.message || 'Authentication failed');
        }
    } catch (error) {
        console.error('Auth error:', error);
        alert('An error occurred during authentication');
    }
}

// Quiz Functions
async function loadNextQuestion() {
    try {
        const response = await fetch('/api/quiz/generate', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!response.ok) throw new Error('Failed to load question');
        
        const data = await response.json();
        currentQuestion = data;
        displayQuestion(data);
    } catch (error) {
        console.error('Error loading question:', error);
        questionText.textContent = 'Failed to load question. Please try again.';
    }
}

function displayQuestion(question) {
    questionText.textContent = question.question;
    optionsContainer.innerHTML = '';
    
    question.options.forEach((option, index) => {
        const optionElement = document.createElement('div');
        optionElement.className = 'option';
        optionElement.textContent = option;
        optionElement.addEventListener('click', () => handleAnswer(index));
        optionsContainer.appendChild(optionElement);
    });
}

async function handleAnswer(selectedIndex) {
    if (!currentQuestion) return;
    
    const isCorrect = selectedIndex === currentQuestion.correct_answer;
    if (isCorrect) {
        score++;
        scoreElement.textContent = score;
    }
    
    // Visual feedback
    const options = optionsContainer.children;
    options[selectedIndex].style.backgroundColor = isCorrect ? '#2ecc71' : '#e74c3c';
    options[currentQuestion.correct_answer].style.backgroundColor = '#2ecc71';
    
    // Submit answer to server
    try {
        await fetch('/api/quiz/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                questionId: currentQuestion.id,
                answer: selectedIndex
            })
        });
        
        // Load next question after delay
        setTimeout(loadNextQuestion, 2000);
    } catch (error) {
        console.error('Error submitting answer:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    if (token) {
        // TODO: Validate token and load user data
        loadNextQuestion();
    }
}); 
