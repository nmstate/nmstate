
use rust_bert::pipelines::common::ModelType;
use rust_bert::pipelines::question_answering::{QuestionAnsweringModel, QaInput};
use std::error::Error;

// process user input and extract relevant information
pub(crate) fn process_input(input_text: &str) -> Result<String, Box<dyn Error>> {
    //  QuestionAnsweringModel
    let qa_model = QuestionAnsweringModel::new(ModelType::Bert);

    let question = "What's the name of the bridge?";

    let qa_input = QaInput {
        question: String::from(question),
        context: String::from(input_text),
    };

    let answers = qa_model.predict(&[qa_input], 1, 32)?;

    let bridge_name = if let Some(answer) = answers.get(0) {
        answer.answer.clone()
    } else {
        String::from("Bridge not found")
    };

    Ok(bridge_name)
}