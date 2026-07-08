Let's create a design doc in ./wip/recursive/.

The topic is creating methods recursively. It will be an evolution of the "/mthds-recursive" skill.

In preparation for that, recent evolution of pipelex (worktree at ../_recursive) enable the lenient validation of .mthds bundles that use pipe signatures.

So you can start from the top-level requirement. Just understand what the user wants in terms of initial input and final output. Design just one pipe signature that will cover this whole job.
This is the starting point of a pipeline design: it captures the client requirements, both in structure (concepts, inputs/output) and in semantics (the description).
And then we should be able to create the details of how the pipe signature can be implemented with actual pipes, which can be pipe operators or pipe controllers. You could start designing one level below. But you could still have some pipe signatures because you're not trying to design the whole thing in one go. You're just working layer by layer.

Do you understand what I mean? Ask me any clarifying questions before you start writing the design doc. 
