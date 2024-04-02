use crate::{
    LinuxBridgeConfig, LinuxBridgeInterface, LinuxBridgePortConfig,
    NetworkPolicy, NetworkState,
};
use rust_bert::pipelines::question_answering::{
    Answer, QaInput, QuestionAnsweringModel,
};
use std::error::Error;

pub(crate) fn nlpm(question: String) {
    let qa_model =
        QuestionAnsweringModel::new(Default::default()).expect("REASON");
    let question_interface = String::from("Get linux bridge ");
    let question_port = String::from("with or using what ");
    let answer_interface: Vec<Vec<Answer>> = qa_model.predict(
        &[QaInput {
            question: question_interface,
            context: question.clone(),
        }],
        1,
        60,
    );
    let answer_port: Vec<Vec<Answer>> = qa_model.predict(
        &[QaInput {
            question: question_port,
            context: question.clone(),
        }],
        1,
        60,
    );

    //let yml: &str = ;

    let content = format!(
        "---
interfaces:
  - name: {:?}
    type: linux-bridge
    state: up
    bridge:
      ports:
        - name: {:?}
        - name: {:?}
    ",
        answer_interface, answer_port, answer_port
    );
    println!("----------Content------------\n{}\n\n", content);
    let mut net_state = serde_yaml::from_str::<NetworkState>(&content);
    //net_state.append_interface_data(crate::Interface::LinuxBridge(lbi.clone()));
    //net_state.set_include_secrets(true);
    //    net_state.retrieve();

    /* nmstate.bridge = LinuxBridgeConfig {
           options: None,
           port: LinuxBridgePortConfig {
               name: "eth1".to_string(),
               ..Default::new()
           },
       };
    */
    let mut cur_state = NetworkState::new();
    cur_state.retrieve();

    //net_state.apply();

    //let diff_state = net_state.gen_diff(&cur_state);

    //let pretty = serde_yaml::to_string(&net_state);
    let pretty_current = serde_yaml::to_string(&cur_state);
    //print!("-----------------NM Diff--------------\n{:?}\n\n", &diff_state);
    //print!("-----------------NM Diff--------------\n{:?}\n\n", serde_yaml::to_string(&diff_state));
    print!(
        "-----------------NM Show Current--------------\n{:#?}\n\n",
        pretty_current
    );
    //print!("-----------------NM Show--------------\n{:?}\n\n", pretty);
    //print!("{:}", qa_model);
    print!(
        "-----------------Bridge--------------\n{:?}\n\n",
        answer_interface
    );
    print!("-----------------Port--------------\n{:?}\n\n", answer_port);
    print!("-----------------NM---------------\n{:?}\n\n", net_state);
}
