document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const resultElement = document.getElementById('prediction-result');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);

        // Clear any previous result messages
        resultElement.textContent = 'Processing...';

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            // Check for response.ok before parsing JSON
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
            }

            const data = await response.json();

            if (data.prediction !== undefined) {
                // Display the prediction result
                resultElement.textContent = `Prediction: ${data.prediction}`;
            } else {
                // Display error message if no prediction is available
                resultElement.textContent = `Error: ${data.error || 'No prediction available'}`;
            }

        } catch (error) {
            console.error("Error:", error);
            // Display error message in resultElement
            resultElement.textContent = `Error: ${error.message}`;
        }
    });
});
