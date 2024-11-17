document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const resultElement = document.getElementById('prediction-result');
    const errorElement = document.getElementById('error-result');  // To display error messages

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        // Clear previous result and error messages
        resultElement.textContent = '';
        errorElement.textContent = '';
        
        const formData = new FormData(form);

        try {
            // Send POST request to Flask API
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            // Check for prediction data and display it
            if (data.prediction !== undefined) {
                resultElement.textContent = `Prediction: ${data.prediction}`;
            } else {
                errorElement.textContent = `Error: ${data.error || 'No prediction available'}`;
            }
        } catch (error) {
            console.error("Error:", error);
            errorElement.textContent = `Error: ${error.message}`;
        }
    });
});
