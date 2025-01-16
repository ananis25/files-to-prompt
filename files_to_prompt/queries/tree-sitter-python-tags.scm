(module . (expression_statement (string) @doc.module))

(class_definition
  name: (identifier) @name.definition.class
  body: (block 
         (expression_statement 
           (string) @doc)?)) @definition.class

(function_definition
  name: (identifier) @name.definition.function
  body: (block 
         (expression_statement 
           (string) @doc)?)) @definition.function

(call
  function: [
      (identifier) @name.reference.call
      (attribute
        attribute: (identifier) @name.reference.call)
  ]) @reference.call

(import_statement) @definition.import

(import_from_statement) @definition.import