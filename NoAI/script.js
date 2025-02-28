// Survey Questions, in order
const questions = [
    "What is your name?",
    "How old are you?",
    "What is your favorite color?",
    "What is your hobby?",
    "Where do you live?"
  ];
  
  // Store user answers
  const userAnswers = Array(questions.length).fill("");
  
  // Track the current question
  let currentQuestionIndex = 0;
  
  // Get references to HTML elements
  const questionContainer = document.getElementById("questionContainer");
  const prevButton = document.getElementById("prevButton");
  const nextButton = document.getElementById("nextButton");
  
  // Function to display a question
  function displayQuestion(index) {
    const questionText = questions[index];
    const userAnswer = userAnswers[index] || "";
  
    questionContainer.innerHTML = `
      <h2 class="text-xl font-bold mb-4">${questionText}</h2>
      <input 
        type="text" 
        id="answerInput" 
        class="w-full border rounded-lg p-2"
        value="${userAnswer}" 
        placeholder="Type your answer here..."
      />
    `;
  
    // Update button visibility
    prevButton.classList.toggle("hidden", index === 0);
    nextButton.textContent = index === questions.length - 1 ? "Submit" : "Next";
  }
  
  // Handle navigation
  prevButton.addEventListener("click", () => {
    saveCurrentAnswer();
    currentQuestionIndex--;
    displayQuestion(currentQuestionIndex);
  });
  
  nextButton.addEventListener("click", () => {
    saveCurrentAnswer();
  
    if (currentQuestionIndex < questions.length - 1) {
      currentQuestionIndex++;
      displayQuestion(currentQuestionIndex);
    } else {
      showResults();
    }
  });
  
  // Save the current answer
  function saveCurrentAnswer() {
    const answerInput = document.getElementById("answerInput");
    userAnswers[currentQuestionIndex] = answerInput.value;
  }
  
  // Show the results
  function showResults() {
    questionContainer.innerHTML = `
      <h2 class="text-xl font-bold mb-4">Survey Completed</h2>
      <ul class="text-left space-y-2">
        ${userAnswers
          .map(
            (answer, index) => `<li><strong>${questions[index]}</strong>: ${answer || "(No answer)"}</li>`
          )
          .join("")}
      </ul>
    `;
    prevButton.classList.add("hidden");
    nextButton.classList.add("hidden");
  }
  
  // Initialize the survey
  displayQuestion(currentQuestionIndex);
  