import org.junit.Test;
import org.junit.Ignore;
import static org.junit.Assert.assertEquals;

public class TestMessageUtil {

  String message = "Robert";
  MessageUtil messageUtil = new MessageUtil(message);

  @Test
  public void testPrintMessage() {
    System.out.println("Inside testPrintMessage()");
    assertEquals(message, messageUtil.printMessage());
  }

  @Test
  public void testSalutationMessage() {
    System.out.println("Inside testSalutationMessage()");
    message = "Hi!" + "Robert";
    assertEquals(message, messageUtil.salutationMessage());
  }

  // Somebody switched this test off "for now" and never came back to it.
  // Mission D in the lab guide is about this test. Leave it alone until then.
  @Ignore("flaky?? passes on my laptop, will look at it next sprint -- Dave")
  @Test
  public void testSalutationIsStable() {
    System.out.println("Inside testSalutationIsStable()");
    messageUtil.salutationMessage();
    assertEquals("Hi!Robert", messageUtil.salutationMessage());
  }
}
