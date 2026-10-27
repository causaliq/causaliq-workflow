# Reducing and standardising quotes usage in workflows

Even as the author of CausalIQ I find it confusing when and where
quotes are needed in workflow matrix and parameter values. Again, my aim is to reduce friction for users, whilst being absolutely clear how the system works.

I think some of the issues may be because we are using off-the-shelf YAML and expression parsers. I think we should continue to use off-the-shelf capablities, but maybe we can preprocess input to them to shield the end-user from their
pecuilarities.

For example, can we dispense with requiring quotes for parameter values - for most of their lifetime they could be handled as strings, but coerced to int or float 'near' the action. Workflow code would attempt to understand strings as parameters first, before assuming they are values.  One remaining need for quotes would be to differentiate a parameter name from a value of the same name i.e. description == "description"